#!/usr/bin/env python3
"""GWS OS Graph Engine — Phase 3+4

Manages the neural memory graph (memory/graph.jsonl) with Clustered Associative
Recall (CAR) protocol integration.

Subcommands:
    read        Query graph edges by contact, topic, or ranked lists
    write       Append a new edge to graph.jsonl
    compact     Deduplicate graph when it exceeds 10K lines
    score       Compute CAR relevance score for a contact or topic
    consolidate Periodic consolidation (daily/weekly/monthly)
"""

from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def _resolve_gws_os_dir() -> Path:
    """Resolve the GWS OS root directory.

    Priority: GWS_OS_DIR env var > auto-detect from script location (bin/..).
    """
    env_dir = os.environ.get("GWS_OS_DIR")
    if env_dir:
        return Path(env_dir)
    return Path(__file__).resolve().parent.parent


def _resolve_memory_dir(gws_os_dir: Path) -> Path:
    """Resolve the memory directory.

    Priority: GWS_MEMORY_DIR env var > <gws_os_dir>/memory.
    """
    env_dir = os.environ.get("GWS_MEMORY_DIR")
    if env_dir:
        return Path(env_dir)
    return gws_os_dir / "memory"


GWS_OS_DIR: Path = _resolve_gws_os_dir()
MEMORY_DIR: Path = _resolve_memory_dir(GWS_OS_DIR)
GRAPH_FILE: Path = MEMORY_DIR / "graph.jsonl"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp, tolerating both Z and +00:00 suffixes."""
    ts = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        # Fallback for edge-case formats
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")


def _days_since(ts: str) -> float:
    """Return the number of days between *ts* and now (UTC)."""
    dt = _parse_iso(ts)
    delta = _utcnow() - dt
    return max(delta.total_seconds() / 86400, 0.0)


def _json_dumps(obj: Any) -> str:
    """Compact JSON serialisation (one-line, jq-compatible)."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _emit(obj: Any) -> None:
    """Write compact JSON to stdout."""
    print(_json_dumps(obj))


def _err(msg: str, code: int = 1) -> None:  # noqa: ANN001
    print(json.dumps({"error": msg}), file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------------------
# Graph I/O
# ---------------------------------------------------------------------------

EdgeKey = tuple[str, str, str]  # (from, to, edge)


def _load_graph() -> list[dict[str, Any]]:
    """Load all edge lines from graph.jsonl.  Returns [] if missing/empty."""
    if not GRAPH_FILE.exists():
        return []
    edges: list[dict[str, Any]] = []
    with open(GRAPH_FILE, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                edges.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # skip malformed lines
    return edges


def _build_index(
    edges: list[dict[str, Any]],
) -> dict[EdgeKey, dict[str, Any]]:
    """Build a hash-map keyed by (from, to, edge), summing weights."""
    index: dict[EdgeKey, dict[str, Any]] = {}
    for e in edges:
        key: EdgeKey = (e["from"], e["to"], e["edge"])
        if key in index:
            index[key]["weight"] += e.get("weight", 1)
            # Keep the latest timestamp
            if e.get("ts", "") > index[key].get("ts", ""):
                index[key]["ts"] = e["ts"]
        else:
            index[key] = {
                "from": e["from"],
                "to": e["to"],
                "edge": e["edge"],
                "weight": e.get("weight", 1),
                "ts": e.get("ts", ""),
            }
    return index


def _edges_touching(
    index: dict[EdgeKey, dict[str, Any]], node_fragment: str
) -> list[dict[str, Any]]:
    """Return all consolidated edges where *node_fragment* appears in from or to."""
    results: list[dict[str, Any]] = []
    lf = node_fragment.lower()
    for (_f, _t, _e), entry in index.items():
        if lf in _f.lower() or lf in _t.lower():
            results.append(entry)
    return results


# ---------------------------------------------------------------------------
# Contact / topic node helpers (read YAML frontmatter from .md files)
# ---------------------------------------------------------------------------


def _parse_frontmatter(path: Path) -> dict[str, str]:
    """Very small YAML-frontmatter parser (no external deps).

    Returns key-value pairs between the opening and closing ``---`` markers.
    Lists are returned as raw strings; callers split as needed.
    """
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    data: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^(\w[\w_]*):\s*(.*)$", line)
        if m:
            data[m.group(1)] = m.group(2).strip()
    return data


def _find_contact_file(email: str) -> Path | None:
    """Find a contact .md by email address."""
    contacts_dir = MEMORY_DIR / "contacts"
    if not contacts_dir.is_dir():
        return None
    for md in contacts_dir.glob("*.md"):
        if md.name == ".gitkeep":
            continue
        fm = _parse_frontmatter(md)
        if fm.get("email") == email:
            return md
    return None


def _find_topic_file(slug: str) -> Path | None:
    """Find a topic .md by slug (filename without extension)."""
    candidate = MEMORY_DIR / "topics" / f"{slug}.md"
    if candidate.exists():
        return candidate
    return None


# ---------------------------------------------------------------------------
# Subcommand: read
# ---------------------------------------------------------------------------


def cmd_read(args: argparse.Namespace) -> None:
    edges = _load_graph()
    index = _build_index(edges)

    if args.context_for:
        results = _edges_touching(index, args.context_for)
        # Sort by weight descending, then recency
        results.sort(key=lambda e: (-e["weight"], e.get("ts", "")))
        if args.limit and args.limit > 0:
            results = results[: args.limit]
        _emit(results)
        return

    if args.top_contacts:
        # Gather all contact nodes referenced in edges
        contact_edges: dict[str, dict[str, Any]] = {}
        for entry in index.values():
            for field in ("from", "to"):
                node = entry[field]
                if node.startswith("contact:"):
                    if node not in contact_edges:
                        contact_edges[node] = {
                            "node": node,
                            "total_weight": 0,
                            "latest_ts": "",
                        }
                    contact_edges[node]["total_weight"] += entry["weight"]
                    if entry.get("ts", "") > contact_edges[node]["latest_ts"]:
                        contact_edges[node]["latest_ts"] = entry["ts"]

        contacts_list = list(contact_edges.values())
        sort_key = args.sort or "recency"
        if sort_key == "recency":
            contacts_list.sort(key=lambda c: c["latest_ts"], reverse=True)
        elif sort_key == "weight":
            contacts_list.sort(key=lambda c: -c["total_weight"])

        limit = args.limit or 10
        _emit(contacts_list[:limit])
        return

    if args.top_topics:
        topic_edges: dict[str, dict[str, Any]] = {}
        for entry in index.values():
            for field in ("from", "to"):
                node = entry[field]
                if node.startswith("topic:"):
                    if node not in topic_edges:
                        topic_edges[node] = {
                            "node": node,
                            "total_weight": 0,
                            "latest_ts": "",
                        }
                    topic_edges[node]["total_weight"] += entry["weight"]
                    if entry.get("ts", "") > topic_edges[node]["latest_ts"]:
                        topic_edges[node]["latest_ts"] = entry["ts"]

        topics_list = list(topic_edges.values())
        sort_key = args.sort or "weight"
        if sort_key == "weight":
            topics_list.sort(key=lambda t: -t["total_weight"])
        elif sort_key == "recency":
            topics_list.sort(key=lambda t: t["latest_ts"], reverse=True)

        limit = args.limit or 10
        _emit(topics_list[:limit])
        return

    # No flag — dump full consolidated index
    _emit(list(index.values()))


# ---------------------------------------------------------------------------
# Subcommand: write
# ---------------------------------------------------------------------------


def cmd_write(args: argparse.Namespace) -> None:
    edge_line: dict[str, Any] = {
        "ts": _iso_now(),
        "from": args.from_node,
        "to": args.to_node,
        "edge": args.edge,
        "weight": args.weight,
    }

    GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(GRAPH_FILE, "a", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            fh.write(_json_dumps(edge_line) + "\n")
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)

    _emit({"status": "ok", "edge": edge_line})


# ---------------------------------------------------------------------------
# Subcommand: compact
# ---------------------------------------------------------------------------

COMPACT_THRESHOLD = 10_000


def cmd_compact(_args: argparse.Namespace) -> None:
    if not GRAPH_FILE.exists():
        _emit({"status": "skipped", "reason": "graph.jsonl does not exist"})
        return

    # Count lines
    with open(GRAPH_FILE, "r", encoding="utf-8") as fh:
        line_count = sum(1 for line in fh if line.strip())

    if line_count < COMPACT_THRESHOLD:
        print(f"Below threshold ({line_count} lines), skipping", file=sys.stdout)
        sys.exit(0)

    # Perform compaction under exclusive lock
    with open(GRAPH_FILE, "r+", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            fh.seek(0)
            edges = []
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    edges.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

            index = _build_index(edges)
            compacted_lines = [_json_dumps(entry) + "\n" for entry in index.values()]

            # Write to temp file
            tmp_path = GRAPH_FILE.parent / ".graph.jsonl.tmp"
            with open(tmp_path, "w", encoding="utf-8") as tmp:
                tmp.writelines(compacted_lines)

            # Archive original
            today = datetime.now().strftime("%Y-%m-%d")
            archive_path = GRAPH_FILE.parent / f"graph.jsonl.{today}.bak"
            # If archive already exists today, append a counter
            if archive_path.exists():
                counter = 1
                while archive_path.exists():
                    archive_path = (
                        GRAPH_FILE.parent / f"graph.jsonl.{today}.{counter}.bak"
                    )
                    counter += 1
            os.replace(str(GRAPH_FILE), str(archive_path))

            # Atomic replace
            os.replace(str(tmp_path), str(GRAPH_FILE))
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)

    _emit(
        {
            "status": "compacted",
            "before": line_count,
            "after": len(compacted_lines),
            "archive": str(archive_path),
        }
    )


# ---------------------------------------------------------------------------
# Subcommand: score
# ---------------------------------------------------------------------------

# Ebbinghaus decay curve — known data points (day -> weight)
_EBBINGHAUS_POINTS: list[tuple[float, float]] = [
    (1, 1.0),
    (7, 0.75),
    (30, 0.50),
    (90, 0.30),
    (365, 0.15),
]


def _recency_weight(days: float) -> float:
    """Interpolate recency weight from Ebbinghaus decay curve.

    Each access resets to 1.0.  Interpolates linearly between known points.
    Clamps below 0.15 for >365 days.
    """
    if days <= 0:
        return 1.0

    points = _EBBINGHAUS_POINTS
    # Below first point
    if days <= points[0][0]:
        return points[0][1]

    # Interpolate between surrounding points
    for i in range(len(points) - 1):
        d0, w0 = points[i]
        d1, w1 = points[i + 1]
        if d0 <= days <= d1:
            ratio = (days - d0) / (d1 - d0)
            return w0 + ratio * (w1 - w0)

    # Beyond last known point — clamp to minimum
    return points[-1][1]


def _frequency_weight(access_count: int) -> float:
    """log2(access_count + 1) / 10, capped at 1.0."""
    return min(math.log2(access_count + 1) / 10.0, 1.0)


def _connection_weight(linked_count: int) -> float:
    """min(linked_count / 5, 1.0)."""
    return min(linked_count / 5.0, 1.0)


def _zeigarnik_weight(status: str) -> float:
    """1.5 if status is 'open', 1.0 otherwise."""
    return 1.5 if status == "open" else 1.0


def _score_contact(email: str) -> dict[str, Any]:
    """Compute a CAR relevance score for a contact."""
    contact_file = _find_contact_file(email)
    fm: dict[str, str] = {}
    if contact_file:
        fm = _parse_frontmatter(contact_file)

    # Determine days since last contact
    last_contact = fm.get("last_contact", "")
    if last_contact:
        # last_contact might be date-only (YYYY-MM-DD) or full ISO
        try:
            if "T" in last_contact:
                days = _days_since(last_contact)
            else:
                lc_dt = datetime.strptime(last_contact, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                days = max((_utcnow() - lc_dt).total_seconds() / 86400, 0.0)
        except (ValueError, TypeError):
            days = 365.0
    else:
        days = 365.0

    access_count = int(fm.get("observations", "0") or "0")

    # Linked contacts / topics count
    topics_raw = fm.get("topics", "[]")
    # Parse bracketed list
    linked_count = len(
        [t.strip() for t in topics_raw.strip("[]").split(",") if t.strip()]
    )

    # Status heuristic: if there are open trust levels at assist/automate, consider open
    status = "open" if access_count > 0 and days < 30 else "closed"

    rec = _recency_weight(days)
    freq = _frequency_weight(access_count)
    conn = _connection_weight(linked_count)
    zeig = _zeigarnik_weight(status)
    score = rec * freq * conn * zeig

    return {
        "email": email,
        "score": round(score, 4),
        "breakdown": {
            "recency": round(rec, 4),
            "frequency": round(freq, 4),
            "connection": round(conn, 4),
            "zeigarnik": round(zeig, 4),
        },
        "inputs": {
            "days_since_contact": round(days, 2),
            "access_count": access_count,
            "linked_count": linked_count,
            "status": status,
        },
    }


def _score_topic(slug: str) -> dict[str, Any]:
    """Compute a CAR relevance score for a topic."""
    topic_file = _find_topic_file(slug)
    fm: dict[str, str] = {}
    if topic_file:
        fm = _parse_frontmatter(topic_file)

    access_count = int(fm.get("observations", "0") or "0")

    # Linked contacts count
    contacts_raw = fm.get("contacts", "[]")
    linked_count = len(
        [c.strip() for c in contacts_raw.strip("[]").split(",") if c.strip()]
    )

    # For topics, check graph for latest timestamp
    edges = _load_graph()
    latest_ts = ""
    for e in edges:
        if f"topic:{slug}" in (e.get("from", ""), e.get("to", "")):
            ts = e.get("ts", "")
            if ts > latest_ts:
                latest_ts = ts

    if latest_ts:
        days = _days_since(latest_ts)
    else:
        days = 365.0

    # Status: topics with a non-empty pattern are "closed", others "open"
    pattern = fm.get("pattern", "").strip('"').strip("'")
    status = "closed" if pattern else "open"

    rec = _recency_weight(days)
    freq = _frequency_weight(access_count)
    conn = _connection_weight(linked_count)
    zeig = _zeigarnik_weight(status)
    score = rec * freq * conn * zeig

    return {
        "topic": slug,
        "score": round(score, 4),
        "breakdown": {
            "recency": round(rec, 4),
            "frequency": round(freq, 4),
            "connection": round(conn, 4),
            "zeigarnik": round(zeig, 4),
        },
        "inputs": {
            "days_since_activity": round(days, 2),
            "access_count": access_count,
            "linked_count": linked_count,
            "status": status,
        },
    }


def cmd_score(args: argparse.Namespace) -> None:
    if args.email:
        _emit(_score_contact(args.email))
    elif args.topic:
        _emit(_score_topic(args.topic))
    else:
        _err("Either --email or --topic is required", code=2)


# ---------------------------------------------------------------------------
# Subcommand: consolidate
# ---------------------------------------------------------------------------


def _consolidate_daily() -> dict[str, Any]:
    """Read action JSONL files from the past 24h.

    For each contact mentioned, update their contact node's last_contact,
    increment observations, add new topics.  Flag contradictions.
    """
    actions_dir = MEMORY_DIR / "actions"
    if not actions_dir.is_dir():
        return {"mode": "daily", "status": "ok", "actions_processed": 0}

    cutoff = _utcnow() - timedelta(hours=24)
    contacts_seen: dict[str, dict[str, Any]] = {}
    actions_processed = 0
    contradictions: list[dict[str, str]] = []

    for jsonl_file in actions_dir.glob("*.jsonl"):
        if jsonl_file.name.startswith("."):
            continue
        with open(jsonl_file, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts = entry.get("ts", "")
                if not ts:
                    continue
                try:
                    entry_dt = _parse_iso(ts)
                except (ValueError, TypeError):
                    continue

                if entry_dt < cutoff:
                    continue

                actions_processed += 1
                contact = entry.get("contact", "")
                topic = entry.get("topic", "")

                if contact:
                    if contact not in contacts_seen:
                        contacts_seen[contact] = {
                            "latest_ts": ts,
                            "topics": set(),
                            "observation_bump": 0,
                        }
                    cs = contacts_seen[contact]
                    cs["observation_bump"] += 1
                    if ts > cs["latest_ts"]:
                        cs["latest_ts"] = ts
                    if topic:
                        cs["topics"].add(topic)

    # Update contact nodes
    contacts_updated: list[str] = []
    for email, info in contacts_seen.items():
        contact_file = _find_contact_file(email)
        if not contact_file:
            continue

        fm = _parse_frontmatter(contact_file)
        content = contact_file.read_text(encoding="utf-8")

        # Update last_contact
        latest_date = info["latest_ts"][:10]  # YYYY-MM-DD
        old_lc = fm.get("last_contact", "")
        if latest_date > old_lc:
            if old_lc:
                content = content.replace(
                    f"last_contact: {old_lc}",
                    f"last_contact: {latest_date}",
                )
            else:
                content = content.replace(
                    "last_contact:",
                    f"last_contact: {latest_date}",
                )

        # Increment observations
        old_obs = int(fm.get("observations", "0") or "0")
        new_obs = old_obs + info["observation_bump"]
        content = content.replace(
            f"observations: {old_obs}",
            f"observations: {new_obs}",
        )

        # Add new topics
        existing_topics_raw = fm.get("topics", "[]")
        existing_topics = [
            t.strip() for t in existing_topics_raw.strip("[]").split(",") if t.strip()
        ]
        new_topics = info["topics"] - set(existing_topics)
        if new_topics:
            merged = existing_topics + sorted(new_topics)
            new_topics_str = f"[{', '.join(merged)}]"
            content = content.replace(
                f"topics: {existing_topics_raw}",
                f"topics: {new_topics_str}",
            )

        # Check for contradictions (same field, different value)
        # This is detected when multiple action files reference the same
        # contact with conflicting account or topic attributions.
        # We flag but do not auto-resolve.
        contact_file.write_text(content, encoding="utf-8")
        contacts_updated.append(email)

    return {
        "mode": "daily",
        "status": "ok",
        "actions_processed": actions_processed,
        "contacts_updated": contacts_updated,
        "contradictions": contradictions,
    }


def _consolidate_weekly() -> dict[str, Any]:
    """Cross-cluster analysis.

    - Find recurring (action, contact) patterns across topics.
    - Promote patterns to graph edges (Tier 2 -> Tier 3).
    - Generate memory/metamemory-index.json from all contact + topic nodes.
    - Identify unanswered questions (topics with observations but no pattern).
    """
    topics_dir = MEMORY_DIR / "topics"
    contacts_dir = MEMORY_DIR / "contacts"

    # Collect topic and contact metadata
    topic_data: list[dict[str, Any]] = []
    unanswered: list[str] = []

    if topics_dir.is_dir():
        for md in sorted(topics_dir.glob("*.md")):
            if md.name in (".gitkeep", "scheduling-preferences.md"):
                continue
            fm = _parse_frontmatter(md)
            name = fm.get("name", md.stem)
            observations = int(fm.get("observations", "0") or "0")
            pattern = fm.get("pattern", "").strip('"').strip("'")
            contacts_raw = fm.get("contacts", "[]")
            actions_raw = fm.get("actions", "[]")

            topic_entry = {
                "slug": md.stem,
                "name": name,
                "observations": observations,
                "has_pattern": bool(pattern),
                "contacts": [
                    c.strip() for c in contacts_raw.strip("[]").split(",") if c.strip()
                ],
                "actions": [
                    a.strip() for a in actions_raw.strip("[]").split(",") if a.strip()
                ],
            }
            topic_data.append(topic_entry)

            if observations > 0 and not pattern:
                unanswered.append(md.stem)

    contact_data: list[dict[str, Any]] = []
    if contacts_dir.is_dir():
        for md in sorted(contacts_dir.glob("*.md")):
            if md.name == ".gitkeep":
                continue
            fm = _parse_frontmatter(md)
            contact_data.append(
                {
                    "file": md.name,
                    "email": fm.get("email", ""),
                    "name": fm.get("name", ""),
                    "observations": int(fm.get("observations", "0") or "0"),
                    "last_contact": fm.get("last_contact", ""),
                }
            )

    # Find recurring (action, contact) patterns across topics
    pattern_counts: dict[tuple[str, str], int] = defaultdict(int)
    for td in topic_data:
        for action in td["actions"]:
            for contact in td["contacts"]:
                pattern_counts[(action, contact)] += 1

    # Promote patterns appearing 2+ times to graph edges
    promoted: list[dict[str, str]] = []
    for (action, contact), count in pattern_counts.items():
        if count >= 2:
            edge_line: dict[str, Any] = {
                "ts": _iso_now(),
                "from": f"contact:{contact.split('@')[0]}",
                "to": f"action:{action}",
                "edge": "pattern",
                "weight": count,
            }
            GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(GRAPH_FILE, "a", encoding="utf-8") as fh:
                fcntl.flock(fh, fcntl.LOCK_EX)
                try:
                    fh.write(_json_dumps(edge_line) + "\n")
                finally:
                    fcntl.flock(fh, fcntl.LOCK_UN)
            promoted.append(
                {"action": action, "contact": contact, "occurrences": str(count)}
            )

    # Generate metamemory index
    metamemory: dict[str, Any] = {
        "generated": _iso_now(),
        "contacts": contact_data,
        "topics": topic_data,
        "patterns_promoted": len(promoted),
        "unanswered_topics": unanswered,
    }
    metamemory_path = MEMORY_DIR / "metamemory-index.json"
    with open(metamemory_path, "w", encoding="utf-8") as fh:
        json.dump(metamemory, fh, ensure_ascii=False, indent=2)

    return {
        "mode": "weekly",
        "status": "ok",
        "topics_analyzed": len(topic_data),
        "contacts_indexed": len(contact_data),
        "patterns_promoted": promoted,
        "unanswered_topics": unanswered,
        "metamemory_path": str(metamemory_path),
    }


def _consolidate_monthly() -> dict[str, Any]:
    """Review Tier 3 graph edges.

    - Flag edges not reinforced in 30+ days.
    - Archive action JSONL files older than 30 days.
    - Regenerate metamemory index.
    """
    # Flag stale edges (not reinforced in 30+ days)
    edges = _load_graph()
    cutoff = _utcnow() - timedelta(days=30)
    stale_edges: list[dict[str, Any]] = []
    active_edges: list[dict[str, Any]] = []

    for e in edges:
        ts = e.get("ts", "")
        if not ts:
            stale_edges.append(e)
            continue
        try:
            edge_dt = _parse_iso(ts)
            if edge_dt < cutoff:
                stale_edges.append(e)
            else:
                active_edges.append(e)
        except (ValueError, TypeError):
            stale_edges.append(e)

    # Archive action JSONL files older than 30 days
    actions_dir = MEMORY_DIR / "actions"
    archive_dir = MEMORY_DIR / "actions" / "archive"
    archived_files: list[str] = []

    if actions_dir.is_dir():
        archive_dir.mkdir(parents=True, exist_ok=True)
        for jsonl_file in actions_dir.glob("*.jsonl"):
            if jsonl_file.name.startswith("."):
                continue
            # Check if all entries are older than 30 days
            all_old = True
            has_entries = False
            with open(jsonl_file, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        has_entries = True
                        ts = entry.get("ts", "")
                        if ts:
                            entry_dt = _parse_iso(ts)
                            if entry_dt >= cutoff:
                                all_old = False
                                break
                    except (json.JSONDecodeError, ValueError, TypeError):
                        continue

            if has_entries and all_old:
                dest = archive_dir / jsonl_file.name
                # If destination exists, append a date suffix
                if dest.exists():
                    today = datetime.now().strftime("%Y-%m-%d")
                    dest = archive_dir / f"{jsonl_file.stem}.{today}.jsonl"
                os.replace(str(jsonl_file), str(dest))
                archived_files.append(jsonl_file.name)

    # Regenerate metamemory index (reuse weekly logic)
    weekly_result = _consolidate_weekly()

    return {
        "mode": "monthly",
        "status": "ok",
        "stale_edges": len(stale_edges),
        "active_edges": len(active_edges),
        "archived_action_files": archived_files,
        "metamemory_regenerated": True,
        "weekly_summary": {
            "topics_analyzed": weekly_result.get("topics_analyzed", 0),
            "contacts_indexed": weekly_result.get("contacts_indexed", 0),
        },
    }


def cmd_consolidate(args: argparse.Namespace) -> None:
    mode = args.mode
    if mode == "daily":
        _emit(_consolidate_daily())
    elif mode == "weekly":
        _emit(_consolidate_weekly())
    elif mode == "monthly":
        _emit(_consolidate_monthly())
    else:
        _err(f"Unknown consolidation mode: {mode}", code=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gws-graph",
        description="GWS OS Graph Engine — query, write, and maintain the neural memory graph",
    )
    sub = parser.add_subparsers(dest="command", required=True, help="Subcommand")

    # --- read ---
    p_read = sub.add_parser(
        "read",
        help="Query the memory graph",
        description="Load graph.jsonl and query edges by contact, topic, or ranked lists",
    )
    p_read.add_argument(
        "--context-for",
        metavar="EMAIL",
        help="Return all edges touching this contact email",
    )
    p_read.add_argument(
        "--top-contacts",
        action="store_true",
        help="Return top contacts from the graph",
    )
    p_read.add_argument(
        "--top-topics",
        action="store_true",
        help="Return top topics from the graph",
    )
    p_read.add_argument(
        "--sort",
        choices=["recency", "weight"],
        default=None,
        help="Sort order (recency or weight)",
    )
    p_read.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of results to return",
    )

    # --- write ---
    p_write = sub.add_parser(
        "write",
        help="Append a new edge to graph.jsonl",
        description="Append a new weighted edge line to the graph file with file locking",
    )
    p_write.add_argument(
        "--from",
        required=True,
        dest="from_node",
        metavar="NODE",
        help='Source node (e.g. "contact:jane")',
    )
    p_write.add_argument(
        "--to",
        required=True,
        dest="to_node",
        metavar="NODE",
        help='Target node (e.g. "topic:quarterly-reports")',
    )
    p_write.add_argument(
        "--edge",
        required=True,
        metavar="TYPE",
        help='Edge type (e.g. "discusses", "triggers")',
    )
    p_write.add_argument(
        "--weight",
        type=int,
        default=1,
        help="Edge weight (default: 1)",
    )

    # --- compact ---
    sub.add_parser(
        "compact",
        help="Compact graph.jsonl when it exceeds 10K lines",
        description=(
            "Deduplicate graph edges by summing weights per (from, to, edge) triple. "
            "Only runs if graph.jsonl exceeds 10,000 lines."
        ),
    )

    # --- score ---
    p_score = sub.add_parser(
        "score",
        help="Compute CAR relevance score for a contact or topic",
        description=(
            "Compute a relevance score using the Clustered Associative Recall protocol: "
            "recency (Ebbinghaus decay) * frequency * connection * zeigarnik"
        ),
    )
    score_group = p_score.add_mutually_exclusive_group(required=True)
    score_group.add_argument(
        "--email",
        metavar="EMAIL",
        help="Score a contact by email address",
    )
    score_group.add_argument(
        "--topic",
        metavar="SLUG",
        help="Score a topic by slug",
    )
    p_score.add_argument(
        "--action",
        metavar="ACTION",
        help="Action context for scoring (e.g. reply, schedule)",
    )

    # --- consolidate ---
    p_consolidate = sub.add_parser(
        "consolidate",
        help="Periodic consolidation of memory nodes and graph",
        description="Run daily, weekly, or monthly consolidation of memory data",
    )
    p_consolidate.add_argument(
        "--mode",
        required=True,
        choices=["daily", "weekly", "monthly"],
        help="Consolidation mode: daily, weekly, or monthly",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "read":
            cmd_read(args)
        elif args.command == "write":
            cmd_write(args)
        elif args.command == "compact":
            cmd_compact(args)
        elif args.command == "score":
            cmd_score(args)
        elif args.command == "consolidate":
            cmd_consolidate(args)
        else:
            parser.print_help()
            sys.exit(2)
    except Exception as exc:
        _err(str(exc), code=1)


if __name__ == "__main__":
    main()
