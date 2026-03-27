# Design: GWS OS — Learning-First Google Workspace CLI Skill Folder

Status: APPROVED

## Problem Statement

Managing multiple Google Workspace accounts is a daily friction multiplier. Gmail's multi-account switching is clunky, no tool provides cross-account intelligence, and existing AI email tools (Superhuman, Email Zero, Inbox Zero) all make the same mistake: they jump straight to automation without first understanding the user's patterns, context, and preferences. The result is automation that creates new friction instead of removing it.

The user wants a CLI-native skill folder for Claude Code that operates across all GWS accounts simultaneously — email, calendar, drive, docs, sheets, contacts — with a learning system that builds understanding over time before graduating to autonomous action.

## What Makes This Cool

Three things no existing tool does:

1. **Learning memory system** — Every interaction builds understanding through contact, topic, and action nodes stored as flat markdown files. The system literally builds a brain as you use it. After a month, it knows that "when Jane from Acme Corp emails about quarterly reports, you usually schedule a call within 2 days and share a Google Doc from the business account." In Phase 3-4, these nodes are connected via a formal graph (JSONL edges, weighted relationships, compaction) for richer pattern detection.

2. **Learning-first, not automation-first** — The system earns trust through a progression: observe (watch patterns) → suggest (propose actions) → assist (execute with confirmation) → automate (act autonomously). Most tools skip to step 4. This one starts at step 1.

3. **Account personas with cross-account orchestration** — Each GWS account has its own context, personality, and rules. But the system sees ACROSS accounts. One command (`/gws morning`) runs all accounts, surfaces what matters, and acts from the right account based on context.

## Constraints

- **Transport layer**: Google's `gws` CLI (open source, March 2026) handles all API access, auth, multi-account, pagination, structured output. We don't build API plumbing. **No MCP fallback** — if `gws` fails validation in Phase 1, the project pivots; it does not fall back to MCP tools.
- **Runtime**: Claude Code skill folder. Each skill is a `.md` file with YAML frontmatter (name, description) and a bash preamble block that runs before Claude processes the skill. The preamble gathers lightweight context (account data, message headers/subjects), and Claude provides the intelligence layer. See gstack skills for reference implementation.
- **Memory**: File-based. Phase 1-2 uses flat markdown files for contact, topic, and action nodes — Claude reads/writes these directly. Phase 3-4 introduces a formal JSONL graph (`graph.jsonl`) with edge weighting, compaction (at 10K lines), and Python query scripts. No database required.
- **Auth**: `gws` handles OAuth per-account. Skill folder manages an account registry that maps accounts to context files.
- **Privacy**: All data stays local. No external services beyond Google's APIs (via `gws`).
- **Memory context budget**: Skills inject a maximum of 10 contact nodes (by recency) and 5 topic nodes (by relevance) per invocation. In Phase 1-2, Claude reads the markdown files directly. In Phase 3-4, Python graph scripts support `--limit`, `--sort`, and `--context-for <email>` flags to retrieve ranked, bounded results including graph edges.

## Premises

1. Google's `gws` CLI is the transport layer — no custom API work needed.
2. Core value = learning orchestration layer (context + memory + patterns).
3. Lives as a Claude Code skill folder (installable like gstack plugins).
4. Multi-account is first-class — all accounts by default, smart routing.
5. Learning progression: observe → suggest → assist → automate.
6. The learning memory system is the differentiator — topics, actions, contacts, and accounts form an interconnected knowledge system (flat markdown in Phase 1-2, formal graph in Phase 3-4) that grows with every interaction.

## Architecture

### Directory Structure

```
~/Projects/gws-os/                # GitHub repo (cloneable)
├── SKILL.md                      # Main entry point
├── setup                         # One-time setup (install gws, configure accounts)
├── accounts/
│   ├── registry.json             # Account list (see schema below)
│   └── personas/
│       ├── business.md           # Persona: formal, VIP contacts, client-first
│       ├── personal.md           # Persona: casual, archive aggressive, protect time
│       └── {custom}.md           # User-defined personas
├── memory/
│   ├── topics/                   # Topic nodes with linked contacts/actions (markdown)
│   ├── contacts/                 # Contact nodes with communication patterns (markdown)
│   ├── actions/                  # Action pattern nodes (what was done, when, why)
│   └── trust-levels.json         # Global defaults / template for new contacts
├── skills/
│   ├── morning.md                # /gws morning — full morning triage
│   ├── triage.md                 # /gws triage — email triage across accounts
│   ├── reply.md                  # /gws reply — context-aware reply from right account
│   ├── plan.md                   # /gws plan — schedule intelligence + conflict detection
│   ├── schedule.md               # /gws schedule — cross-calendar scheduling
│   ├── followup.md               # /gws followup — track and remind follow-ups
│   ├── search.md                 # /gws search — cross-account, cross-service search
│   ├── brief.md                  # /gws brief — pre-meeting context assembly
│   ├── weekly.md                 # /gws weekly — weekly review and pattern report
│   ├── learn.md                  # /gws learn — show what the system has learned
│   └── onboard.md               # /gws onboard — interactive setup questionnaire
├── hooks/
│   ├── post-action.sh            # After any gws action: log to memory nodes
│   └── pattern-detect.sh         # Runs after post-action.sh when any node hits 5+ observations
├── tests/                        # Tests ship with each phase (see Implementation Phases)
│   ├── test_phase1/              # Phase 1 tests
│   └── ...
├── docs/
│   └── ARCHITECTURE.md           # Technical architecture reference
│
│ # Phase 3-4 additions (not present in Phase 1-2):
│ # ├── bin/
│ # │   ├── gws-graph-read.py     # Python: query the neural memory graph
│ # │   ├── gws-graph-write.py    # Python: write nodes/edges to graph
│ # │   └── gws-graph-compact.py  # Python: merge edges when graph.jsonl > 10K lines
│ # └── memory/
│ #     └── graph.jsonl            # Neural memory graph (append-only edge log)
```

### Account Registry Schema

```json
{
  "accounts": [
    {
      "id": "business",
      "email": "you@company.com",
      "label": "Work",
      "persona": "personas/business.md",
      "gws_profile": "business",
      "is_default": true,
      "scan_window": "24h"
    },
    {
      "id": "personal",
      "email": "you@gmail.com",
      "label": "Personal",
      "persona": "personas/personal.md",
      "gws_profile": "personal",
      "is_default": false,
      "scan_window": "24h"
    }
  ],
  "default_account": "business"
}
```

Fields: `id` (unique short name), `email` (GWS account email), `label` (display name), `persona` (relative path to persona markdown file), `gws_profile` (profile name in `gws` credential store), `is_default` (used when account can't be inferred from context), `scan_window` (how far back skills scan for this account — default `"24h"`, configurable per account: `"24h"`, `"1w"`, `"1y"`, etc.).

### Setup Flow

The `setup` script is idempotent and handles:
1. **Check dependencies** — Verify `gws` is installed (`gws --version`). If not, install via the published package method. If install fails, report error and suggest manual install. Also verify `jq` is installed; if not, suggest `brew install jq`.
2. **Validate minimum `gws` features** — Run `gws gmail messages list --limit 1` to confirm Gmail API access works. Run `gws calendar events list --limit 1` for Calendar. If either fails, setup aborts with a clear error — no fallback.
3. **Account setup wizard** — For each account: prompt for email, label, persona choice, scan_window (default: "24h"). Run `gws auth login --profile <id>` to authenticate. Store in `registry.json`.
4. **Initialize memory** — Create `memory/` directories (contacts/, topics/, actions/), seed `trust-levels.json` with global defaults.
5. **Verify** — Run a test triage on the first account to confirm end-to-end flow works.

Output: "GWS OS setup complete. X accounts configured. Run `/gws onboard` to configure personas, or `/gws triage` to start."
If already set up: "GWS OS already configured. X accounts active. Run `setup --add` to add an account."

### Memory Access (Phase 1-2)

In Phase 1-2, Claude reads and writes memory nodes (contacts, topics, actions) as flat markdown files directly. No scripts, no JSONL graph, no programmatic query layer. Skills read the markdown files in their preamble to build context.

Example: to find context for a contact, the skill preamble reads `memory/contacts/jane-smith.md` directly. To update a contact after an interaction, Claude writes back to the same file.

### Graph Query Interface (Phase 3-4)

When the formal graph is introduced in Phase 3-4, Python scripts become the programmatic interface for reading, writing, and compacting the graph:

```bash
# Read operations (called by skills during preamble)
python bin/gws-graph-read.py --context-for "jane@acme.com" --limit 10
python bin/gws-graph-read.py --top-contacts --sort recency --limit 10
python bin/gws-graph-read.py --top-topics --sort weight --limit 5

# Write operations (called by hooks and skills)
python bin/gws-graph-write.py add-edge --from "contact:jane" --to "topic:quarterly-reports" --edge "discusses"
python bin/gws-graph-write.py log-action --action "reply" --account "business" --contact "jane@acme.com"

# Maintenance
python bin/gws-graph-compact.py    # Merge edges when graph.jsonl > 10K lines
```

**Write semantics**: Write operations always append a new event line to `graph.jsonl`. The query layer sums weights across all lines for a given `(from, to, edge)` triple at read time. Compaction consolidates duplicates into a single line with the summed weight and archives the raw log.

**Performance**: The graph read script loads `graph.jsonl` into an in-memory hash-map (keyed by node ID) once per invocation. For files under 10K lines, this completes in <1s on modern hardware.

### Neural Memory System

The memory system is the brain of GWS OS. In Phase 1-2, it stores three types of nodes as flat markdown files that Claude reads/writes directly. In Phase 3-4, a fourth layer (graph edges in `graph.jsonl`) adds weighted relationships between nodes.

**Contact nodes** (`memory/contacts/{hash}.md`):
```markdown
---
email: jane@acme.com
name: Jane Smith
accounts_seen: [business]          # references account id from registry
topics: [quarterly-reports, performance-marketing, reporting]
communication_pattern: formal, responsive, expects quick turnarounds
last_contact: 2026-03-25
frequency: 3-4x/week
observations: 18                    # total interactions observed with this contact
trust_levels:
  reply: assist       # system can draft replies, user confirms
  archive: automate   # system archives without asking
  schedule: suggest   # system suggests but waits for confirmation
---
```

**Contact nodes are the single source of truth for trust levels.** `trust-levels.json` is only a template/global defaults file used when creating new contacts (e.g., `{"archive": "automate"}` as a starting default for all new contacts). Once a contact node exists, its trust levels are authoritative — the global file is never consulted again for that contact. Trust promotion counters (consecutive accepts/confirms) are tracked in a `_streak` field on each contact action: e.g., `reply_streak: 3`.

**Topic nodes** (`memory/topics/{slug}.md`):
```markdown
---
name: Quarterly Reporting
contacts: [jane@acme.com, team@acme.com]
accounts: [business]               # references account id from registry
actions: [reply, schedule-call, share-doc]
pattern: "Quarterly report emails → schedule review call within 48h → share updated doc"
confidence: 0.6    # = min(observations / 20, 1.0) — 12/20 = 0.6
observations: 12
---
```

**Action nodes** (`memory/actions/{type}.jsonl`):
Each line is an observed action with context:
```json
{"ts":"2026-03-25T10:30:00Z","action":"reply","account":"business","contact":"jane@acme.com","topic":"quarterly-reports","trust":"assist","latency_min":15,"user_edited":true}
```

**Graph edges** (`memory/graph.jsonl`) — **Phase 3-4 only**:
Append-only log of weighted relationships between nodes. Not present in Phase 1-2 (Claude infers relationships from the markdown nodes directly).
```json
{"ts":"...","from":"contact:jane","to":"topic:quarterly-reports","edge":"discusses","weight":12}
{"ts":"...","from":"topic:quarterly-reports","to":"action:schedule-call","edge":"triggers","weight":8}
{"ts":"...","from":"action:reply","to":"account:business","edge":"uses","weight":25}
```

### Trust Progression System

Every action type has a trust level that progresses independently:

| Level | Behavior | Example |
|-------|----------|---------|
| **observe** | System watches, logs to memory, says nothing | New contact pattern |
| **suggest** | System proposes action, waits for user | "Jane emailed about the Q1 report — schedule a call?" |
| **assist** | System drafts action, user confirms before send | Pre-drafted reply shown for approval |
| **automate** | System acts autonomously for non-send actions, logs result | Auto-archives newsletters, auto-blocks focus time |

**Confirmation gate on all send/reply/schedule actions**: Regardless of trust level, ALL actions that send an email, reply to a thread, or create/modify a calendar event require explicit user confirmation before execution. Trust level affects *drafting autonomy* (how much the system prepares without asking), not *sending autonomy*. A contact at `automate` trust for `reply` means the system auto-drafts the reply — but still shows it for confirmation before sending.

Trust is earned per action type (reply, archive, schedule, etc.) AND per context (contact, topic, account). The system might be at `automate` for archiving newsletters but `suggest` for replying to clients.

**Promotion criteria** (configurable):
- observe → suggest: 5+ consistent observations of the same `(action_type, contact)` pair logged without a user override
- suggest → assist: user accepted suggestion 3+ consecutive times for that `(action_type, contact)` pair
- assist → automate: user confirmed without edits 5+ consecutive times for that `(action_type, contact)` pair

A "consistent observation" means the same `(action_type, contact)` pair was logged and the user did not override. Streaks are tracked in the contact node's `{action}_streak` field and reset to 0 on any override.

**Demotion**: A user override drops trust one level for that action+context pair. An "override" is defined as:
- User **edits** a drafted reply before sending (assist → suggest for that contact+action)
- User **rejects** a suggested action (suggest → observe for that topic+action)
- User **undoes** an automated action — e.g., unarchives something the system archived (automate → assist)
- User **manually performs** an action the system offered to handle — e.g., sending a reply the system was about to draft (assist → suggest)
- User explicitly says "don't do that" during any skill execution (drops to observe immediately)

NOT an override: user confirming an action without changes, user ignoring a suggestion (no demotion — just no promotion).

### Account Persona System

Each account has a persona file that shapes how Claude behaves:

```markdown
# Persona: Business (you@company.com)

## Identity
- Formal tone, professional language
- Sign-off: "Best, [Name]"
- Response time expectation: same business day

## Priorities
1. Client emails (Acme Corp, agency clients)
2. Operations issues
3. Team coordination
4. Everything else

## VIP Contacts
- Jane Smith (Acme Corp) — always respond within 2 hours
- [other VIPs from contact nodes]

## Rules
- Never auto-archive client emails
- Schedule follow-ups for any email requiring action
- Block 30min after client calls for notes

## Calendar
- Business hours: 09:00-18:00 (your timezone)
- No meetings before 10:00
- Friday: half day, no new meetings
```

### Skill File Format

Each skill is a `.md` file following the Claude Code skill convention:

```markdown
---
name: gws-triage
description: Triage emails across all GWS accounts with AI-powered categorization
---

## Preamble

\```bash
# Verify dependencies
command -v jq >/dev/null 2>&1 || { echo "ERROR: jq required. Run: brew install jq"; exit 1; }
command -v gws >/dev/null 2>&1 || { echo "ERROR: gws not installed. Run /gws setup"; exit 1; }

# Load account registry
ACCOUNTS=$(cat ~/Projects/gws-os/accounts/registry.json)

# Pull unread HEADERS ONLY from each account (lightweight — no message bodies)
for PROFILE in $(echo "$ACCOUNTS" | jq -r '.accounts[].gws_profile'); do
  SCAN_WINDOW=$(echo "$ACCOUNTS" | jq -r --arg p "$PROFILE" '.accounts[] | select(.gws_profile==$p) | .scan_window // "24h"')
  echo "=== Account: $PROFILE (window: $SCAN_WINDOW) ==="
  gws gmail messages list --profile "$PROFILE" --query "is:unread newer_than:${SCAN_WINDOW}" --format json --fields "id,from,subject,date" --limit 50 2>&1
done
\```

## Instructions

You are the GWS Triage skill. Using the email headers above, read contact nodes
from `~/Projects/gws-os/memory/contacts/` for any known senders. Fetch full
message bodies on-demand only for emails you need to act on.
[skill prompt continues]
```

The preamble runs first (via Bash), its output becomes context for Claude, then Claude follows the Instructions section. **Preambles fetch headers/subjects only** — full message bodies are fetched on-demand when Claude needs them during skill execution.

### Core Skills

**`/gws onboard`** — Interactive setup questionnaire (Phase 1):
1. Run an interactive questionnaire to configure account personas (tone, priorities, VIP contacts, calendar rules)
2. Configure user SOPs (response time expectations, archiving preferences, follow-up cadence)
3. User can skip any question to accept sensible defaults
4. Writes persona files to `accounts/personas/` and seeds initial contact nodes if provided
5. Can be re-run at any time to update preferences

**`/gws morning`** — The flagship skill. Runs every morning:
1. Pull unread from all accounts via `gws`
2. Classify using account personas + memory nodes
3. Surface top priorities across accounts. Priority is an ordered sort (not a weighted sum): first by VIP status (binary — VIPs always on top), then by topic relevance (descending), then by trust level as tiebreaker, then by recency. Claude applies this ranking heuristically using the memory context from the preamble.
4. Suggest actions based on learned patterns
5. Execute confirmed actions from the right account
6. Log everything to memory nodes

**`/gws followup`** — Track and remind follow-ups:
1. Scan sent emails across accounts for threads awaiting response
2. Cross-reference with contact nodes for expected response patterns
3. Surface overdue follow-ups ranked by importance
4. Suggest nudge drafts for stale threads

**`/gws triage`** — Focused email triage:
1. Pull unread/starred from specified or all accounts
2. Categorize: urgent / needs-reply / FYI / archive
3. Apply account-specific rules from personas
4. Show triage dashboard with recommended actions
5. Batch-execute confirmed actions

**`/gws reply`** — Context-aware reply:
1. Read email thread
2. Read contact node + topic node from memory
3. Load account persona for tone/style
4. Draft reply matching learned patterns
5. **User confirms before send** (mandatory — regardless of trust level)
6. Log to memory (action node updates, contact node updates)

**`/gws schedule`** — Cross-calendar scheduling:
1. Pull free/busy from all account calendars
2. Apply persona rules (no meetings before 10, etc.)
3. Find optimal slots respecting all constraints
4. **User confirms before creating event** (mandatory — regardless of trust level)
5. Create event on the right calendar, send invites from the right account

**`/gws plan`** — Multi-calendar planning assistant (schedule intelligence):
1. Pull events from all account calendars (next 7 days by default)
2. Merge into a unified cross-account timeline
3. Analyze schedule for conflicts **beyond time overlaps**:
   - **Location conflicts**: back-to-back meetings in different physical locations with no travel buffer
   - **Energy conflicts**: 3+ heavy meetings in a row with no break, high-stakes meeting after a draining block
   - **Prep time conflicts**: VIP/client meeting with no prep window, presentation with no review time
   - **Persona rule violations**: meetings outside business hours, on half-days, before start time
   - **Pattern-based flags**: meeting types with high cancel rates, attendees who run over, topics that need follow-ups
4. Present flags with severity levels: BLOCK (will cause a real problem), WARN (likely friction), NOTE (worth knowing)
5. When scheduling new events: score slots by quality (not just availability), suggest top 2-3 with reasoning
6. **Confirmation gate** on all calendar modifications (mandatory)
7. **Learn from responses**: user acts on flag → strengthen it; user dismisses 3+ times → suppress; user provides new info ("I'm in the office Tuesdays") → save as scheduling rule
8. Maintain `memory/topics/scheduling-preferences.md` as a living document of learned scheduling rules, dismissed flags, and active flags

**`/gws brief`** — Pre-meeting intelligence:
1. Look up meeting attendees in contact nodes
2. Pull recent email threads with each attendee
3. Surface relevant topics and action items
4. Compile 1-page brief with context from across accounts

**`/gws search`** — Cross-account, cross-service search:
1. Accept a natural language query (e.g., "find the quarterly report Jane sent last week")
2. Parse intent: identify target service (email, calendar, drive), accounts, and contacts from memory
3. Run `gws` search commands across relevant accounts in parallel (or sequentially if serial)
4. Merge and deduplicate results across accounts
5. Present results grouped by service and ranked by relevance + memory context

**`/gws weekly`** — Weekly review and learning report:
1. Summarize actions taken this week across accounts
2. Show new patterns detected (reads from `memory/topics/` — pattern detection is done by `pattern-detect.sh` hook, not by this skill)
3. Report trust level changes
4. Surface follow-ups that are overdue
5. Highlight emerging patterns that could graduate to higher trust levels

**`/gws learn`** — Transparency and undo skill:
1. Show what the system has learned about contacts, topics, patterns (reads from `memory/topics/` and `memory/contacts/`)
2. Display current trust levels per contact and per action type
3. Allow user to correct/override learned patterns
4. Show memory statistics (node counts, confidence scores; edge/graph stats available in Phase 3-4)
5. **Undo automated actions**: Show today's automated action log (`memory/actions/automate-log-{date}.jsonl`). User can select actions to reverse — e.g., unarchive emails, cancel scheduled events. Skills operating at `automate` trust MUST log all actions to this daily file.

### Automated Action Logging

Skills that execute at `automate` trust level write to `memory/actions/automate-log-{date}.jsonl`:
```json
{"ts":"...","action":"archive","account":"business","message_id":"msg123","subject":"Newsletter","reversible":true,"reverse_cmd":"gws gmail messages modify --add-labels INBOX --profile business msg123"}
```
Each entry includes the reverse command needed to undo it. `/gws learn` reads this file and presents undo options.

### Error Handling

Every skill handles failures gracefully:

| Error | Behavior |
|-------|----------|
| `gws` not installed | Skill aborts with: "Run `/gws setup` first" |
| OAuth token expired | Attempt `gws auth refresh --profile <id>`. If fails: "Account {label} needs re-auth. Run `gws auth login --profile <id>`" and skip that account, continue with others |
| Rate limited (429) | Back off 5s, retry once. If still limited: "Google rate limit hit for {account}. Showing partial results." |
| Network timeout | Skip account, continue with others. Note which accounts were unreachable. |
| Empty inbox | Not an error — report "No unread messages in {account}" and continue |
| Memory read failure | Degrade gracefully — run without memory context, warn: "Memory nodes unavailable. Running without learned context." |
| `gws` CLI unstable/broken | Skill aborts with: "`gws` CLI is not functional. GWS OS requires a working `gws` installation — no fallback available." |

### Implementation Phases

**Phase 1: Foundation (Days 1-3)**
- Set up skill folder structure (GitHub repo at `~/Projects/gws-os/`)
- Install and validate `gws` CLI (**gate**: if `gws` fails validation, the project pivots — no MCP fallback)
- Build account registry (with `scan_window` per account) + persona system
- Create flat markdown memory nodes (contacts/, topics/, actions/) — Claude reads/writes directly
- Implement `/gws onboard` (interactive questionnaire for personas + SOPs, or skip to defaults)
- Implement `/gws triage` (email only, single account — scaffolding phase; multi-account comes in Phase 2)
- **Phase 1 tests**: setup validation, account registry CRUD, triage single-account, onboard flow

**Phase 2: Multi-Account + Memory (Days 4-7)**
- Extend triage to multi-account (respecting per-account `scan_window`)
- Build pattern observer hook (writes to markdown nodes)
- Implement contact/topic/action node creation and updates
- Create trust level system (contact nodes as source of truth, `trust-levels.json` as template only)
- Implement `/gws morning` and `/gws reply` (with mandatory confirmation gate on send)
- **Phase 2 tests**: multi-account triage, contact node CRUD, trust level resolution (contact > global), confirmation gate enforcement

**Phase 3: CAR Protocol + Graph Engine**
- CAR Protocol integrated: three-tier memory (Tier 1 raw episodes, Tier 2 compressed summaries with CAR metadata, Tier 3 graph schemas)
- Single Python graph engine (`bin/gws-graph.py`) with 5 subcommands: read, write, compact, score, consolidate
- Relevance scoring formula: recency (Ebbinghaus decay with access reset) * frequency * connection * zeigarnik
- Consolidation pipeline: daily (Tier 1 to Tier 2), weekly (Tier 2 to Tier 3 + metamemory-index.json)
- File locking with `fcntl.flock()` on writes, atomic rename on compact
- Implement `/gws schedule` with cross-calendar support (mandatory confirmation gate on event creation)
- Implement `/gws plan` — multi-calendar planning assistant with conflict detection beyond time overlaps, schedule scoring, and learning from user responses (maintains `memory/topics/scheduling-preferences.md`)
- Implement `/gws brief` with cross-service context
- Implement `/gws followup`
- **Phase 3 tests**: graph engine (read/write/compact/score/consolidate), CAR protocol tiers, relevance scoring, cross-calendar scheduling, brief assembly

**Phase 4: CAR Protocol Learning Engine**
- Trust progression with demotion: observe to suggest to assist to automate, promotion via streak >= threshold, demotion on user override (drops one level, resets streak, logs disagreement to memory)
- Cross-domain pattern detection via consolidation pipeline (weekly Tier 2 to Tier 3 analysis)
- Metamemory index (`memory/metamemory-index.json`): knowledge inventory tracking coverage, confidence, known gaps, unanswered questions — generated by weekly consolidation
- Prospective memory triggers (`memory/prospective.jsonl`): forward-planted reminders checked at session start, fire on condition match, expire when stale
- Build `/gws weekly` and `/gws learn`
- `pattern-detect.sh`: triggered by `post-action.sh` when a contact/topic node reaches 5+ observations. Reads aggregated action nodes for that contact, identifies recurring `(action, topic)` sequences, writes a `pattern` field to the topic node `.md`. Feeds trust promotion: if a detected pattern matches a promotion threshold, updates the contact node's trust level.
- Graph compaction mechanism (auto-compact at 10K lines)
- Documentation and packaging
- **Phase 4 tests**: trust progression/demotion with disagreement memory, prospective memory triggers, metamemory generation, consolidation pipeline, pattern detection, graph compaction, weekly/learn skills

**CAR Protocol deferred to v2:** Question-based encoding (Section 4), thinking profile (Section 10), conversational momentum (Section 10.4).

**Future (v2 backlog):**
- `/gws focus` — Protect deep work time across calendars (DND modes, calendar blocking)
- `/gws drive` — Cross-account Drive search and file sharing
- `/gws docs` — Auto-create meeting docs, shared notes

## Open Questions

1. **`gws` CLI maturity** — Released March 2026, only weeks old. Phase 1 includes a validation gate. If it fails, the project pivots (no MCP fallback).
2. **Concurrent account access** — Can `gws` run parallel requests across accounts, or does it serialize? Test in Phase 1. If serial, skills will iterate accounts sequentially (slower but functional).

**Resolved (no longer open):**
- ~~MCP vs CLI~~ → gws CLI only. No MCP fallback. If gws fails, the project pivots. (Decision #4)
- ~~Graph scaling~~ → Compaction at 10K lines via `gws-graph-compact.py` in Phase 3-4. (Decision #1)
- ~~Offline graph queries~~ → Phase 1-2: Claude reads markdown directly. Phase 3-4: Python graph scripts with ranked/limited retrieval. (Decision #1, #2)
- ~~Graph in Phase 1~~ → Deferred to Phase 3-4. Phase 1-2 uses flat markdown only. (Decision #1)
- ~~Bin scripts in Phase 1-2~~ → Removed. Claude reads/writes markdown directly. `bin/` introduced in Phase 3-4 with Python scripts. (Decision #7)
- ~~Trust source of truth~~ → Contact nodes are authoritative. `trust-levels.json` is a template for new contacts only. (Decision #6)
- ~~Send autonomy at automate trust~~ → All send/reply/schedule actions require user confirmation regardless of trust level. (Decision #10)

## Success Criteria

- [ ] `/gws morning` runs across 2+ accounts and surfaces priorities in under 30 seconds (assumes parallel account access; if serial, target adjusts to 60 seconds)
- [ ] Memory nodes grow automatically from daily use without manual intervention
- [ ] Trust level for newsletter/bulk-email archiving reaches `automate` within 2 weeks of use (requires minimum 13 archive confirmations per promotion rules)
- [ ] Contact nodes correctly link to topics after 10+ interactions
- [ ] System correctly routes replies to the right account 95%+ of the time
- [ ] `/gws weekly` shows meaningful pattern insights after 1 week of use

## Distribution Plan

- Open-source GitHub repo at https://github.com/cheeky-amit/gws-os (MIT license)
- Install: `git clone https://github.com/cheeky-amit/gws-os.git ~/Projects/gws-os` then run `bash setup`
- Requires: `gws` CLI (`brew install googleworkspace-cli`), `jq` (`brew install jq`), Claude Code, Google OAuth credentials per account
- Setup script handles `gws` validation and account configuration
- `/gws onboard` runs an interactive questionnaire for persona and SOP setup (or skip to defaults)
- README with installation instructions, example personas, and contribution guide
- License: MIT

## Next Steps

1. **Create GitHub repo** — Initialize `~/Projects/gws-os/` with the Phase 1-2 directory structure (no `bin/`, no `graph.jsonl`).
2. **Validate `gws` CLI** — Install it, test multi-account auth, run basic Gmail/Calendar commands. Confirm it's stable enough to build on. If it fails, pivot — no MCP fallback.
3. **Build `/gws onboard`** — Interactive questionnaire for account personas and user SOPs.
4. **Build `/gws triage`** — Start with single-account email triage (headers-only preamble, on-demand body fetch). Get the core loop working.
5. **Add memory nodes** — Start logging actions and building contact/topic nodes as flat markdown files.
6. **Write Phase 1 tests** — Validate setup, registry, onboard, and single-account triage.
7. **Extend to multi-account** — Add cross-account orchestration with per-account `scan_window`.

## Resolved Decisions (Eng Review, 2026-03-27)

The following 11 decisions were made during engineering review and are incorporated throughout this document:

| # | Decision | Impact |
|---|----------|--------|
| 1 | Defer graph to Phase 3-4 | Phase 1-2 uses flat markdown files only. No `graph.jsonl`, no graph scripts, no edge weighting. Graph query interface, compaction, and JSONL format move to Phase 3-4. |
| 2 | Python for graph scripts | Phase 3-4 graph scripts are Python: `gws-graph-read.py`, `gws-graph-write.py`, `gws-graph-compact.py` (not bash bin scripts). |
| 3 | Tests alongside each phase | Tests ship with the phase they test, not deferred. Phase 1 has Phase 1 tests, etc. |
| 4 | gws CLI only — no MCP fallback | Removed all MCP fallback mentions. Pure gws CLI product. If gws fails validation, the project pivots. |
| 5 | Lightweight preamble | Skill preambles fetch headers/subjects only (not full message bodies). Full detail fetched on-demand. |
| 6 | Trust state on contact nodes | Contact nodes are the single source of truth for trust levels. `trust-levels.json` is only a template for new contacts. |
| 7 | No bin scripts Phase 1-2 | `bin/` directory removed from Phase 1-2 structure. Claude reads/writes markdown directly. `bin/` (Python) introduced in Phase 3-4. |
| 8 | New `/gws onboard` skill in Phase 1 | Interactive questionnaire to configure account personas and user SOPs, or skip to sensible defaults. |
| 9 | Configurable `scan_window` per account | Added `scan_window` field to account registry (default: `"24h"`). Each account can have a different scan window. |
| 10 | Confirmation gate on all send/reply | All send/reply/schedule actions require explicit user confirmation regardless of trust level. Trust affects drafting autonomy, not sending autonomy. |
| 11 | Open-source via GitHub repo | Distribution changed from `~/.claude/skills/gws-os/` to GitHub repo at `~/Projects/gws-os/`. All paths updated. |

