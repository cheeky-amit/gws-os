# GWS OS

**A learning-first Google Workspace operating system for Claude Code.**

One CLI. All your accounts. Memory that grows with you.

---

## What It Does

GWS OS turns Claude Code into a Google Workspace power user across multiple accounts simultaneously. It reads your email, calendar, and drive — then learns your patterns over time.

```
/gws morning
```

```
=== Work (you@company.com) ===

URGENT (1)
  Jane Smith — "Q1 Report Review" — 2h ago
  > Last 12 interactions. Trust: assist (drafts replies for you).
  > Suggested: Draft reply + schedule review call within 48h.

NEEDS-REPLY (3)
  Team — "Sprint planning agenda" — 5h ago
  Bank — "Wire confirmation" — yesterday
  Vendor — "Project budget review" — 3 days ago

ARCHIVE (6)
  Newsletters, notifications, promotions — auto-archived.

=== Personal (you@gmail.com) ===
  No unread messages.

What would you like to do?
```

No dashboards. No web UI. Just your terminal.

---

## How It's Different

Most AI email tools jump straight to automation. GWS OS earns trust first.

### The Trust Progression

```
observe  -->  suggest  -->  assist  -->  automate
  |              |             |             |
 watch        propose       draft       act alone
 & learn      & wait       & confirm    (non-send only)
```

Trust is earned **per action type** and **per contact**. The system might auto-archive newsletters but still ask before replying to clients. And it never sends without your confirmation — ever.

### Memory That Grows

Every interaction builds understanding:

```
memory/contacts/jane-smith.md
---
email: jane@acme.com
name: Jane Smith
topics: [quarterly-reports, performance-marketing, reporting]
communication_pattern: formal, responsive, expects quick turnarounds
frequency: 3-4x/week
observations: 18
trust_levels:
  reply: assist       # drafts replies, you confirm
  archive: automate   # archives without asking
  schedule: suggest   # suggests, waits for you
---
```

After a month, the system knows that when Jane emails about quarterly reports, you usually schedule a call within 2 days and share a Google Doc from the business account.

### Schedule Intelligence

Most calendar tools find free slots. GWS OS thinks about what those slots **mean**.

```
/gws plan

FLAG: BLOCK  location-conflict
  "Sprint Review" (office) → "Dentist" (across town) — 0min gap
  You can't physically get there in time.
  Suggestion: Move Sprint Review 30min earlier, or switch to Zoom.

FLAG: WARN  no-prep-time
  "Acme Corp Q1 Review" with Jane Smith (VIP) — no buffer before
  Last 12 meetings with Jane required prep. You usually review the report first.
  Suggestion: Block 15min before for prep.

FLAG: NOTE  heavy-day
  5 meetings, 4h 30min total — only one 30min break.
  Consider declining or moving one non-critical meeting.
```

The system learns from your responses. Dismiss a flag 3 times? It stops flagging it. Act on it? It flags harder next time. Different rules for client meetings vs internal standups — learned, not configured.

### Multi-Account, Single Brain

Each account has its own persona (tone, priorities, VIP contacts, calendar rules). But the system sees across all accounts with one command.

---

## Commands

| Command | What It Does |
|---------|-------------|
| `/gws onboard` | Configure personas, priorities, and preferences |
| `/gws triage` | Categorize and act on unread email |
| `/gws morning` | Full morning brief across all accounts |
| `/gws reply` | Context-aware reply from the right account |
| `/gws plan` | Schedule intelligence — flags conflicts, learns preferences |
| `/gws schedule` | Cross-calendar scheduling with persona rules |
| `/gws brief` | Pre-meeting intelligence on attendees |
| `/gws followup` | Track threads awaiting response |
| `/gws search` | Cross-account, cross-service search |
| `/gws weekly` | Weekly patterns and learning report |
| `/gws learn` | See what the system knows + undo actions |

---

## Quick Start

### Prerequisites

- [Claude Code](https://claude.ai/claude-code) installed
- [gws CLI](https://github.com/googleworkspace/cli) (`brew install googleworkspace-cli`)
- `jq` (`brew install jq`)

### Install

```bash
git clone https://github.com/cheeky-amit/gws-os.git ~/Projects/gws-os
cd ~/Projects/gws-os
bash setup
```

The setup script will:
1. Verify `gws` and `jq` are installed
2. Validate Gmail and Calendar API access
3. Walk you through account configuration (email, label, scan window)
4. Initialize memory directories
5. Seed persona templates

### First Run

```bash
# Configure your preferences (or skip to defaults)
/gws onboard

# Start triaging
/gws triage
```

---

## Architecture

```
~/Projects/gws-os/
├── SKILL.md               # Skill entry point
├── setup                   # One-time setup
├── bin/
│   └── gws-graph.py       # Graph engine (read/write/score/consolidate/compact)
├── lib/
│   ├── gws-common.sh       # Shared library (sourced by all skills)
│   └── templates/           # Contact + topic node templates
├── accounts/
│   ├── registry.json       # Your accounts + scan windows
│   └── personas/           # Tone, priorities, VIPs per account
├── memory/
│   ├── contacts/           # Who you talk to + trust levels
│   ├── topics/             # What you talk about + patterns
│   └── actions/            # What you've done (action logs)
├── skills/                 # All 11 /gws commands
├── hooks/                  # Post-action logging + pattern detection
├── tests/                  # pytest — 82 tests across Phase 1-4
└── docs/                   # Design doc, architecture, case study
```

### Shared Library (`lib/gws-common.sh`)

Every skill sources one file. No duplicated boilerplate.

```bash
# What a skill preamble looks like now (2 lines)
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/gws-common.sh"
gws_init

# Then use shared functions
for PROFILE in $(get_profiles); do
    LABEL=$(get_account_field "$PROFILE" label)
    gws_clean "$PROFILE" gmail users messages list --params '...' --format json
done

# Memory operations
create_contact "jane@acme.com" "Jane Smith" "work"
trust=$(resolve_trust "jane@acme.com" "reply")  # contact node > global defaults
log_action "reply" "work" "jane@acme.com" "quarterly-reports"
```

### Three-Tier Memory (CAR Protocol)

Memory follows the [Clustered Associative Recall Protocol](docs/car-protocol.pdf), inspired by how human memory actually works.

```
Tier 1: Raw Episodes (memory/actions/*.jsonl)
  7-30 day retention. Every email read, reply sent, meeting scheduled.

Tier 2: Compressed Summaries (memory/contacts/*.md, memory/topics/*.md)
  Months retention. "Jane is formal, responds quickly, discusses Q1 reports."

Tier 3: Schemas & Patterns (memory/graph.jsonl)
  Permanent. Weighted edges between contacts, topics, actions.
  "When Jane emails about reports, you usually schedule a call within 48h."
```

Consolidation promotes memories up the tiers: daily (Tier 1→2), weekly (Tier 2→3), monthly (review + archive).

### Graph Engine (`bin/gws-graph.py`)

Single Python script, 5 subcommands, zero dependencies beyond stdlib.

```bash
python3 bin/gws-graph.py read --context-for "jane@acme.com"  # query
python3 bin/gws-graph.py write --from "contact:jane" --to "topic:reports" --edge "discusses"
python3 bin/gws-graph.py score --email "jane@acme.com"       # relevance scoring
python3 bin/gws-graph.py consolidate --mode weekly            # tier promotion
python3 bin/gws-graph.py compact                              # merge edges >10K lines
```

### Built on `gws` CLI

[Google Workspace CLI](https://github.com/googleworkspace/cli) — a Rust binary that maps 1:1 to Google's APIs. GWS OS calls it directly via bash. No MCP wrappers, no proxy servers, no third-party dependencies.

```bash
# What gws looks like
gws gmail users messages list --params '{"userId":"me","maxResults":20}' --format json
gws calendar events list --params '{"calendarId":"primary"}' --format json
```

Multi-account is handled via isolated config directories per account:

```bash
GOOGLE_WORKSPACE_CLI_CONFIG_DIR="~/.config/gws-profiles/business" gws gmail ...
GOOGLE_WORKSPACE_CLI_CONFIG_DIR="~/.config/gws-profiles/personal" gws gmail ...
```

### Memory System

**Phase 1-2:** Flat markdown files. Claude reads and writes them directly. Simple, debuggable, human-readable.

**Phase 3-4:** JSONL graph with weighted edges between contacts, topics, and actions. Python scripts for querying and compaction.

---

## Design Principles

1. **Learning-first, not automation-first.** Observe before suggesting. Suggest before drafting. Draft before acting.

2. **Confirmation gate on all sends.** Trust affects drafting autonomy, not sending autonomy. The system never sends an email or creates a calendar event without your explicit OK.

3. **Contact nodes are truth.** Each contact carries their own trust levels. Global defaults are just templates for new contacts.

4. **Lightweight by default.** Skill preambles fetch headers only. Full message bodies are fetched on-demand when needed.

5. **No vendor lock-in.** Everything is local files. Memory is markdown you can read with `cat`. Leave anytime.

6. **Memory is reconstruction, not retrieval.** The system synthesizes answers from fragments across tiers, scores by relevance, and gets slightly better every session. Based on the CAR Protocol.

---

## Production Validation

GWS OS is built on patterns validated in production across 10+ days of daily use managing 8+ brands:

- **500-800+ gws invocations** with zero auth failures
- **50-80 calls per session** (morning brief + intel sweep + ad-hoc)
- **<1s** per Gmail list, **<2s** per full message read
- Replaced a fragile MCP-proxy chain with a single local binary

See [`docs/gws-case-study.md`](docs/gws-case-study.md) for the full case study.

---

## Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| **1** | Foundation — setup, onboard, triage (single account) | Done |
| **2** | Multi-account + shared library + memory CRUD + trust resolution | Done |
| **3** | JSONL graph + CAR Protocol + calendar + plan/brief/followup/search | Done |
| **4** | Trust progression + consolidation + metamemory + pattern detection | Done |

---

## Contributing

GWS OS is open source. PRs welcome.

```bash
# Run all tests (82 tests across 4 phases)
python3 -m pytest tests/ -v

# Phase 1 tests (setup, registry, structure)
python3 -m pytest tests/test_phase1/ -v

# Phase 2 tests (CRUD, trust resolution, actions)
python3 -m pytest tests/test_phase2/ -v
```

Tests ship alongside each phase. See [`docs/design.md`](docs/design.md) for the full design document.

---

## License

MIT

---

*Built for people who live in the terminal.*
