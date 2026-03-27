"""Phase 3 tests: gws-graph.py graph engine (read, write, compact, score, consolidate)."""

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCRIPT = Path(__file__).parent.parent.parent / "bin" / "gws-graph.py"


def run_graph(
    tmp_path: Path, subcmd: str, *args: str
) -> subprocess.CompletedProcess[str]:
    """Run gws-graph.py with the given subcommand inside a temp GWS OS dir."""
    env = os.environ.copy()
    env["GWS_OS_DIR"] = str(tmp_path)
    env["GWS_MEMORY_DIR"] = str(tmp_path / "memory")
    result = subprocess.run(
        ["python3", str(SCRIPT), subcmd, *args],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    return result


def write_edge(
    tmp_path: Path,
    from_node: str,
    to_node: str,
    edge: str,
    weight: int = 1,
) -> subprocess.CompletedProcess[str]:
    """Shorthand to write a single edge via the CLI."""
    return run_graph(
        tmp_path,
        "write",
        "--from",
        from_node,
        "--to",
        to_node,
        "--edge",
        edge,
        "--weight",
        str(weight),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def graph_env(tmp_path: Path) -> Path:
    """Create the minimal directory structure expected by the graph engine."""
    (tmp_path / "memory" / "contacts").mkdir(parents=True)
    (tmp_path / "memory" / "topics").mkdir(parents=True)
    (tmp_path / "memory" / "actions").mkdir(parents=True)
    return tmp_path


# ---------------------------------------------------------------------------
# TestGraphRead
# ---------------------------------------------------------------------------


class TestGraphRead:
    """Tests for the 'read' subcommand."""

    def test_read_empty_graph(self, graph_env: Path) -> None:
        """No graph.jsonl exists -- read returns []."""
        result = run_graph(graph_env, "read")
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data == []

    def test_read_context_for_email(self, graph_env: Path) -> None:
        """Add edges, query by email fragment, get related edges."""
        write_edge(graph_env, "contact:jane", "topic:reports", "discusses")
        write_edge(graph_env, "contact:jane", "topic:budgets", "reviews")
        write_edge(graph_env, "contact:bob", "topic:hiring", "discusses")

        result = run_graph(graph_env, "read", "--context-for", "jane")
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert len(data) == 2
        nodes = {e["to"] for e in data}
        assert "topic:reports" in nodes
        assert "topic:budgets" in nodes

    def test_read_top_contacts_by_recency(self, graph_env: Path) -> None:
        """Returns contacts sorted by most recent edge (default for --top-contacts)."""
        # Write edges with explicit timestamps to ensure deterministic ordering
        graph_file = graph_env / "memory" / "graph.jsonl"
        graph_file.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            json.dumps(
                {
                    "ts": "2026-03-01T10:00:00Z",
                    "from": "contact:jane",
                    "to": "topic:reports",
                    "edge": "discusses",
                    "weight": 1,
                },
                separators=(",", ":"),
            ),
            json.dumps(
                {
                    "ts": "2026-03-02T10:00:00Z",
                    "from": "contact:bob",
                    "to": "topic:hiring",
                    "edge": "discusses",
                    "weight": 1,
                },
                separators=(",", ":"),
            ),
        ]
        graph_file.write_text("\n".join(lines) + "\n")

        result = run_graph(
            graph_env,
            "read",
            "--top-contacts",
            "--sort",
            "recency",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert len(data) == 2
        # bob has the later timestamp
        assert data[0]["node"] == "contact:bob"
        assert data[1]["node"] == "contact:jane"

    def test_read_top_topics_by_weight(self, graph_env: Path) -> None:
        """Returns topics sorted by edge weight sum (default for --top-topics)."""
        write_edge(graph_env, "contact:jane", "topic:reports", "discusses", weight=5)
        write_edge(graph_env, "contact:bob", "topic:hiring", "discusses", weight=10)

        result = run_graph(
            graph_env,
            "read",
            "--top-topics",
            "--sort",
            "weight",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert len(data) == 2
        assert data[0]["node"] == "topic:hiring"
        assert data[0]["total_weight"] == 10
        assert data[1]["node"] == "topic:reports"
        assert data[1]["total_weight"] == 5

    def test_read_deduplicates_edges(self, graph_env: Path) -> None:
        """Same (from, to, edge) appears twice; weights are summed in the index."""
        write_edge(graph_env, "contact:jane", "topic:reports", "discusses", weight=3)
        write_edge(graph_env, "contact:jane", "topic:reports", "discusses", weight=7)

        result = run_graph(graph_env, "read")
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert len(data) == 1
        assert data[0]["weight"] == 10


# ---------------------------------------------------------------------------
# TestGraphWrite
# ---------------------------------------------------------------------------


class TestGraphWrite:
    """Tests for the 'write' subcommand."""

    def test_write_creates_file(self, graph_env: Path) -> None:
        """Writing to a non-existent graph.jsonl creates the file."""
        graph_file = graph_env / "memory" / "graph.jsonl"
        assert not graph_file.exists()

        result = write_edge(graph_env, "contact:jane", "topic:reports", "discusses")
        assert result.returncode == 0

        assert graph_file.exists()
        lines = [l for l in graph_file.read_text().splitlines() if l.strip()]
        assert len(lines) == 1

    def test_write_appends_edge(self, graph_env: Path) -> None:
        """Writing two edges results in a file with 2 lines."""
        write_edge(graph_env, "contact:jane", "topic:reports", "discusses")
        write_edge(graph_env, "contact:bob", "topic:hiring", "discusses")

        graph_file = graph_env / "memory" / "graph.jsonl"
        lines = [l for l in graph_file.read_text().splitlines() if l.strip()]
        assert len(lines) == 2

    def test_write_has_timestamp(self, graph_env: Path) -> None:
        """Written edge has a 'ts' field in ISO 8601 format."""
        write_edge(graph_env, "contact:jane", "topic:reports", "discusses")

        graph_file = graph_env / "memory" / "graph.jsonl"
        edge = json.loads(graph_file.read_text().splitlines()[0])
        assert "ts" in edge
        # Validate ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", edge["ts"]), (
            f"Unexpected timestamp format: {edge['ts']}"
        )


# ---------------------------------------------------------------------------
# TestGraphCompact
# ---------------------------------------------------------------------------


class TestGraphCompact:
    """Tests for the 'compact' subcommand."""

    def test_compact_below_threshold(self, graph_env: Path) -> None:
        """graph.jsonl has <10K lines -- prints skip message, exits 0."""
        # Write a few edges (well below 10K)
        for i in range(5):
            write_edge(graph_env, f"contact:user{i}", "topic:test", "discusses")

        result = run_graph(graph_env, "compact")
        assert result.returncode == 0
        assert "Below threshold" in result.stdout

    def test_compact_merges_duplicates(self, graph_env: Path) -> None:
        """Create >10K lines with duplicates; compact merges them, weight summed."""
        graph_file = graph_env / "memory" / "graph.jsonl"
        graph_file.parent.mkdir(parents=True, exist_ok=True)

        # Write 10001 identical edge lines directly for speed
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        edge_line = json.dumps(
            {
                "ts": ts,
                "from": "contact:jane",
                "to": "topic:reports",
                "edge": "discusses",
                "weight": 1,
            },
            separators=(",", ":"),
        )
        with open(graph_file, "w", encoding="utf-8") as fh:
            for _ in range(10_001):
                fh.write(edge_line + "\n")

        result = run_graph(graph_env, "compact")
        assert result.returncode == 0

        output = json.loads(result.stdout.strip())
        assert output["status"] == "compacted"
        assert output["before"] == 10_001
        assert output["after"] == 1  # all duplicates merged

        # Verify the compacted file has exactly 1 line with summed weight
        compacted = [l for l in graph_file.read_text().splitlines() if l.strip()]
        assert len(compacted) == 1
        entry = json.loads(compacted[0])
        assert entry["weight"] == 10_001


# ---------------------------------------------------------------------------
# TestGraphScore
# ---------------------------------------------------------------------------


class TestGraphScore:
    """Tests for the 'score' subcommand."""

    def _create_contact_md(
        self,
        graph_env: Path,
        email: str,
        *,
        observations: int = 0,
        status: str = "closed",
        topics: str = "[]",
        last_contact: str = "",
    ) -> Path:
        """Create a contact .md file with YAML frontmatter."""
        slug = email.split("@")[0].replace(".", "-")
        content = f"""---
email: {email}
name: Test User
observations: {observations}
topics: {topics}
last_contact: {last_contact}
---
"""
        path = graph_env / "memory" / "contacts" / f"{slug}.md"
        path.write_text(content, encoding="utf-8")
        return path

    def test_score_new_contact(self, graph_env: Path) -> None:
        """Contact with 0 observations returns a valid score dict."""
        self._create_contact_md(graph_env, "new@test.com", observations=0)

        result = run_graph(graph_env, "score", "--email", "new@test.com")
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())

        assert "score" in data
        assert "breakdown" in data
        assert isinstance(data["score"], (int, float))
        assert data["inputs"]["access_count"] == 0

    def test_score_open_thread_bonus(self, graph_env: Path) -> None:
        """Contact with status:open (observations>0, recent) gets 1.5x zeigarnik."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._create_contact_md(
            graph_env,
            "active@test.com",
            observations=5,
            topics="[reports, budgets]",
            last_contact=today,
        )

        result = run_graph(graph_env, "score", "--email", "active@test.com")
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())

        # The score logic sets status="open" when access_count > 0 and days < 30
        assert data["breakdown"]["zeigarnik"] == 1.5
        assert data["inputs"]["status"] == "open"

    def test_score_closed_thread_no_bonus(self, graph_env: Path) -> None:
        """Contact with status:resolved (observations=0 or old) gets 1.0x zeigarnik."""
        self._create_contact_md(
            graph_env,
            "old@test.com",
            observations=0,
            last_contact="2020-01-01",
        )

        result = run_graph(graph_env, "score", "--email", "old@test.com")
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())

        assert data["breakdown"]["zeigarnik"] == 1.0
        assert data["inputs"]["status"] == "closed"


# ---------------------------------------------------------------------------
# TestConsolidation
# ---------------------------------------------------------------------------


class TestConsolidation:
    """Tests for the 'consolidate' subcommand."""

    def test_consolidate_daily_updates_contacts(self, graph_env: Path) -> None:
        """Action JSONL from today -> contact node observations incremented."""
        # Create a contact node
        contact_content = """---
email: jane@test.com
name: Jane Test
observations: 5
topics: [reports]
last_contact: 2026-01-01
---
"""
        contact_file = graph_env / "memory" / "contacts" / "jane-test.md"
        contact_file.write_text(contact_content, encoding="utf-8")

        # Create an action JSONL with today's timestamp
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        action_entry = json.dumps(
            {
                "ts": ts,
                "action": "reply",
                "contact": "jane@test.com",
                "topic": "reports",
                "account": "work",
            }
        )
        action_file = graph_env / "memory" / "actions" / "reply.jsonl"
        action_file.write_text(action_entry + "\n", encoding="utf-8")

        result = run_graph(graph_env, "consolidate", "--mode", "daily")
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())

        assert data["mode"] == "daily"
        assert data["status"] == "ok"
        assert data["actions_processed"] == 1
        assert "jane@test.com" in data["contacts_updated"]

        # Verify observations incremented from 5 to 6
        updated = contact_file.read_text(encoding="utf-8")
        assert "observations: 6" in updated

    def test_consolidate_weekly_generates_metamemory(self, graph_env: Path) -> None:
        """Weekly consolidation creates metamemory-index.json."""
        # Create a minimal topic node
        topic_content = """---
name: Quarterly Reports
observations: 3
contacts: [jane@test.com]
actions: [reply, archive]
pattern:
---
"""
        topic_file = graph_env / "memory" / "topics" / "quarterly-reports.md"
        topic_file.write_text(topic_content, encoding="utf-8")

        # Create a minimal contact node
        contact_content = """---
email: jane@test.com
name: Jane Test
observations: 5
last_contact: 2026-03-20
---
"""
        contact_file = graph_env / "memory" / "contacts" / "jane-test.md"
        contact_file.write_text(contact_content, encoding="utf-8")

        result = run_graph(graph_env, "consolidate", "--mode", "weekly")
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())

        assert data["mode"] == "weekly"
        assert data["status"] == "ok"
        assert data["topics_analyzed"] == 1
        assert data["contacts_indexed"] == 1

        # Verify metamemory-index.json was created
        metamemory_path = graph_env / "memory" / "metamemory-index.json"
        assert metamemory_path.exists()

        metamemory = json.loads(metamemory_path.read_text(encoding="utf-8"))
        assert "contacts" in metamemory
        assert "topics" in metamemory
        assert len(metamemory["contacts"]) == 1
        assert len(metamemory["topics"]) == 1
        assert metamemory["contacts"][0]["email"] == "jane@test.com"

        # Topic without a pattern should appear in unanswered
        assert "quarterly-reports" in metamemory["unanswered_topics"]
