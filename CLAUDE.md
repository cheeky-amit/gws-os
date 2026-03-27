# GWS OS — Learning-First Google Workspace CLI

## What This Is
Open-source Claude Code skill folder that orchestrates multiple Google Workspace accounts with a learning memory system. Built on the `gws` CLI (Google Workspace CLI, Rust binary, Apache-2.0).

## Architecture
- **Transport**: `gws` CLI handles all Google API access — no MCP fallback
- **Memory**: Flat markdown files (Phase 1-2), JSONL graph (Phase 3-4)
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
├── accounts/
│   ├── registry.json      # Account list (gitignored, user-specific)
│   └── personas/
│       └── example.md     # Example persona template
├── memory/
│   ├── contacts/          # Contact nodes (markdown, gitignored)
│   ├── topics/            # Topic nodes (markdown, gitignored)
│   ├── actions/           # Action logs (JSONL, gitignored)
│   └── trust-levels.json  # Global defaults template (gitignored)
├── skills/
│   ├── onboard.md         # /gws onboard — interactive setup
│   ├── triage.md          # /gws triage — email triage
│   ├── morning.md         # /gws morning (Phase 2)
│   ├── reply.md           # /gws reply (Phase 2)
│   └── ...
├── hooks/
│   ├── post-action.sh     # Log actions to memory
│   └── pattern-detect.sh  # Detect patterns at 5+ observations
├── tests/
│   └── test_phase1/       # Phase 1 tests (pytest)
└── docs/
    ├── ARCHITECTURE.md    # Technical reference
    └── design.md          # Full design doc
```

## Commands
```bash
# Run tests
pytest tests/ -v

# Run Phase 1 tests only
pytest tests/test_phase1/ -v

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
