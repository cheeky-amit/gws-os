# GWS OS — Learning-First Google Workspace CLI

## What This Is
Open-source Claude Code skill folder that orchestrates multiple Google Workspace accounts with a learning memory system. Built on the `gws` CLI (Google Workspace CLI, Rust binary, Apache-2.0).

## Architecture
- **Transport**: `gws` CLI handles all Google API access — no MCP fallback
- **Memory**: Flat markdown files (Phase 1-2), JSONL graph (Phase 3-4). Memory follows the Clustered Associative Recall (CAR) Protocol — three-tier storage, relevance scoring, consolidation jobs.
- **Skills**: `.md` files with bash preambles + Claude instructions
- **Trust**: observe → suggest → assist → automate (per action+contact)
- **Confirmation gate**: ALL send/reply/schedule actions require user confirmation regardless of trust level

## Key Design Decisions
1. gws CLI only — no MCP fallback (if gws breaks, we pivot)
2. Phase 1-2: flat markdown, Claude reads/writes directly. No bin scripts, no graph.jsonl
3. Phase 3-4: Python graph scripts (`bin/gws-graph-*.py`), JSONL edges
4. Contact nodes are single source of truth for trust levels
5. Lightweight preambles (headers only, bodies on-demand)
6. `scan_window` per account in registry.json
7. CAR Protocol for memory architecture (three-tier: actions → contacts/topics → graph edges)
8. Single Python graph engine (bin/gws-graph.py) with 5 subcommands
9. Relevance scoring at retrieval time (recency * frequency * connection * zeigarnik)
10. Prospective memory triggers (forward-planted reminders that fire on conditions)

## gws CLI Notes (from validation)
- **Version**: 0.16.0 installed (0.18.1 available)
- **Command pattern**: `gws <service> <resource> <method> --params '<JSON>' [--json '<body>']`
- **Multi-account**: No native `--profile`. Use `GOOGLE_WORKSPACE_CLI_CONFIG_DIR` env var per account
- **Email send**: Requires base64url-encoded RFC 2822 in `raw` field
- **Output**: `--format json` (default), also table/yaml/csv. `--page-all` for NDJSON pagination
- **Errors**: Structured JSON to stderr, exit codes 0/1/2/3
- **Quirk**: Prints `"Using keyring backend: keyring"` to stdout before JSON — strip with `grep -v '^Using keyring backend:'`
- **Base64 bodies**: Gmail API returns email bodies as base64-encoded strings in `payload.parts` — decode when reading full messages
- **Dry run**: `--dry-run` for safe validation
- **Schema**: `gws schema <method>` for API introspection

## Directory Structure
```
gws-os/
├── CLAUDE.md              # This file
├── SKILL.md               # Main entry point (skill registration)
├── setup                  # One-time setup script (bash)
├── bin/
│   └── gws-graph.py       # Graph engine (read/write/compact/score/consolidate)
├── lib/
│   ├── gws-common.sh      # Shared library (all skills source this)
│   └── templates/          # Node templates (contact.md, topic.md)
├── accounts/
│   ├── registry.json      # Account list (gitignored, user-specific)
│   └── personas/
│       └── example.md     # Example persona template
├── memory/
│   ├── contacts/          # Contact nodes (markdown, gitignored)
│   ├── topics/            # Topic nodes (markdown, gitignored)
│   ├── actions/           # Action logs (JSONL, gitignored)
│   ├── trust-levels.json  # Global defaults template (gitignored)
│   ├── graph.jsonl        # Graph edges (runtime, gitignored)
│   ├── metamemory-index.json  # Metamemory index (runtime, gitignored)
│   └── prospective.jsonl  # Prospective memory triggers (runtime, gitignored)
├── skills/
│   ├── onboard.md         # /gws onboard — interactive setup
│   ├── triage.md          # /gws triage — email triage
│   ├── morning.md         # /gws morning — daily brief
│   ├── reply.md           # /gws reply — context-aware reply
│   └── ...                # 11 skills total (see SKILL.md)
├── hooks/
│   ├── post-action.sh     # Log actions to memory
│   └── pattern-detect.sh  # Detect patterns at 5+ observations
├── tests/
│   ├── test_phase1/       # Phase 1 tests (setup, registry, structure)
│   ├── test_phase2/       # Phase 2 tests (CRUD, trust, actions)
│   ├── test_phase3/       # Phase 3 tests (graph engine, CAR protocol)
│   └── test_phase4/       # Phase 4 tests (prospective memory, consolidation)
└── docs/
    ├── ARCHITECTURE.md    # Technical reference
    └── design.md          # Full design doc
```

## Shared Library (lib/gws-common.sh)
All skills source this. Key functions:
- `gws_init` — validate deps, load registry, set globals
- `gws_clean <profile> <args>` — profile-aware gws wrapper, strips keyring output
- `get_profiles` / `get_account_field` / `get_default_profile` — registry access
- `create_contact` / `update_contact` / `get_contact` — contact node CRUD
- `resolve_trust <email> <action>` — trust resolution (contact > global defaults)
- `log_action <action> <account> <email> [topic]` — log + auto-update contact
- `print_contacts` / `print_topics` / `print_personas` / `print_memory_summary` — preamble helpers
- `promote_trust` / `demote_trust` / `check_promotion` / `log_disagreement` — trust lifecycle
- `graph_query` / `graph_write` / `graph_score` / `graph_consolidate` — graph engine wrappers
- `create_trigger` / `check_triggers` — prospective memory triggers
- `print_metamemory` — metamemory index display

## Commands
```bash
# Run all tests (82 tests across Phase 1-4)
python3 -m pytest tests/ -v

# Run Phase 1 tests only
python3 -m pytest tests/test_phase1/ -v

# Run Phase 2 tests only
python3 -m pytest tests/test_phase2/ -v

# Run Phase 3 tests
python3 -m pytest tests/test_phase3/ -v

# Run Phase 4 tests
python3 -m pytest tests/test_phase4/ -v

# Graph engine
python3 bin/gws-graph.py read --context-for "jane@acme.com" --limit 10
python3 bin/gws-graph.py write --from "contact:jane" --to "topic:reports" --edge "discusses"
python3 bin/gws-graph.py compact
python3 bin/gws-graph.py score --email "jane@acme.com"
python3 bin/gws-graph.py consolidate --mode daily

# Validate gws CLI
gws --version
gws gmail users messages list --params '{"userId":"me","maxResults":1}' --format json

# Multi-account wrapper
gws-profile() {
  local profile="$1"; shift
  GOOGLE_WORKSPACE_CLI_CONFIG_DIR="$HOME/.config/gws-profiles/$profile" gws "$@"
}
```

## Conventions
- Python: PEP 8, type annotations, ruff format/lint
- Tests: pytest, alongside each phase
- Git: conventional commits (feat|fix|refactor|docs|test|chore)
- Skills: YAML frontmatter + bash preamble + Claude instructions
- Memory nodes: YAML frontmatter in markdown files
