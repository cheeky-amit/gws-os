# GWS OS Architecture

See the full design doc at `docs/design.md` for comprehensive details.

## Transport Layer

All Google API access goes through the `gws` CLI (google workspace CLI, Rust binary).

### Command Pattern
```
gws <service> <resource> <method> --params '<JSON>' [--json '<body>'] [--format json]
```

### Multi-Account
No native profile flag. Each account uses an isolated config directory:
```bash
GOOGLE_WORKSPACE_CLI_CONFIG_DIR="$HOME/.config/gws-profiles/$PROFILE" gws <command>
```

### Email Send
Requires base64url-encoded RFC 2822 message in the `raw` field:
```bash
gws gmail users messages send --params '{"userId":"me"}' --json '{"raw":"<base64url>"}'
```

## Memory System

### Phase 1-2: Flat Markdown
Claude reads/writes markdown files directly. No scripts, no graph.

- `memory/contacts/{name}.md` — YAML frontmatter with trust levels, observation counts
- `memory/topics/{slug}.md` — YAML frontmatter with linked contacts, patterns
- `memory/actions/{type}.jsonl` — Append-only action logs

### Phase 3-4: JSONL Graph
Python scripts (`bin/gws-graph-*.py`) manage a formal graph with weighted edges.

## Trust Progression

```
observe → suggest → assist → automate
```

- Per action type AND per contact
- Contact nodes are source of truth (not trust-levels.json)
- **ALL send/reply/schedule actions require user confirmation regardless of trust level**

## Skill Execution Flow

1. Bash preamble runs → fetches headers, reads registry, reads memory nodes
2. Preamble output becomes context for Claude
3. Claude analyzes, categorizes, proposes actions
4. User confirms destructive/send actions
5. Post-action hook logs to memory
