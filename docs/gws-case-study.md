# Case Study: gws CLI as the Google Workspace Backbone of an AI-Powered Operation

> **gws version:** 0.16.0
> **Period:** March 2026 (4+ weeks in production)
> **Setup:** macOS, Homebrew install, single-user OAuth, AES-256-GCM encrypted credentials

---

## Context

I run operations across multiple business units and accounts. My operating model is **me + Claude Code (Anthropic's AI CLI)** — no dashboards, no web UI. Everything happens in the terminal.

Before gws, I relied on Composio MCP servers to bridge Google Workspace into my AI workflows. That meant:
- HTTP proxy to a third-party backend for every Gmail/Calendar/Drive call
- OAuth tokens managed externally (expired unpredictably)
- JSON-over-HTTP latency for simple reads
- A dependency on a startup's uptime for my daily operations

**gws replaced all of that with a single local binary.**

---

## The Multi-Account Problem

I manage two Google Workspace accounts:

| Account | Purpose |
|---------|---------|
| Primary account | Gmail, Calendar, Drive, Sheets, Tasks, Docs |
| Secondary account (different org) | Gmail, Calendar for a subset of projects |

### Current Setup

**Primary account** — gws CLI with full OAuth:
- Dedicated GCP project with OAuth Desktop app client
- 10 scopes: Gmail (modify), Calendar, Drive, Sheets, Docs, Presentations, Tasks
- 43 APIs enabled
- Credentials: AES-256-GCM encrypted at `~/.config/gws/credentials.enc`, key in OS keyring
- Token auto-refresh via cached refresh token

**Secondary account** — still on Composio MCP as fallback:
- SSE transport to Composio backend
- Used only when gws primary fails or for projects managed under the secondary org

### What Multi-Account Support Would Unlock

Right now, switching accounts requires re-authenticating or maintaining the Composio bridge for the secondary. What I'd want:

```bash
# Dream API
gws --profile agency gmail users messages list --params '...'
gws --profile secondary gmail users messages list --params '...'

# Or via env var
GWS_PROFILE=secondary gws gmail users messages list --params '...'
```

With named profiles, I could:
1. Drop Composio entirely for Google Workspace
2. Run parallel sweeps across both accounts in a single command
3. Keep credentials isolated per account (separate GCP projects)

---

## How gws Fits Into the Stack

```
┌─────────────────────────────────────────────┐
│              Claude Code (terminal)          │
│                                              │
│   /morning  /brief  /sweep  /sync  /recap    │
│         ↓       ↓      ↓      ↓       ↓     │
│   ┌─────────────────────────────────────┐    │
│   │         gws CLI (primary)           │    │
│   │  Gmail · Calendar · Drive · Sheets  │    │
│   │  Tasks · Docs · Presentations       │    │
│   └──────────────┬──────────────────────┘    │
│                  │ fallback                   │
│   ┌──────────────▼──────────────────────┐    │
│   │       Composio MCP (secondary)      │    │
│   │  Gmail · Calendar (2nd account)     │    │
│   └─────────────────────────────────────┘    │
│                                              │
│   Other MCPs: chat · project management ·     │
│   analytics · web scraping · vector search    │
└─────────────────────────────────────────────┘
```

gws is called directly by Claude Code via `Bash` tool — no MCP wrapper needed. The AI constructs the exact `gws gmail users messages list` command, executes it, and parses the JSON output.

---

## Integration Points (9 Files)

gws is wired into **5 workflow commands** and **4 agent definitions**:

### Workflow Commands

| Command | What gws Does |
|---------|--------------|
| `/morning` | Reads inbox (last 24h), sent mail, today's calendar. Detects what was already handled. |
| `/brief <topic>` | Searches Gmail by topic keywords (inbox + sent), pulls 7-day calendar events with attendees. |
| `/sweep` | Dispatches parallel sub-agents — Gmail agent and Calendar agent both use gws as primary. Sweeps inbox, sent, and calendar across configurable time windows. |
| `/sync <topic>` | 30-day deep pull — all Gmail threads + Drive files for a specific topic. |
| `/recap` | Searches sent mail for weekly activity, drafts recap emails via gws. |

### Agent Definitions

| Agent | gws Usage |
|-------|----------|
| Strategy Agent | Gmail search + Calendar for strategic context |
| Comms Agent | Gmail drafts + Calendar for comms execution |
| Deals Agent | Gmail search for deal-related threads |
| Ops Agent | Calendar + Gmail for scheduling and ops |

### Example: Morning Brief Gmail Sweep

```bash
# 1. Inbox scan (skip promotions/social)
gws gmail users messages list --params '{
  "userId": "me",
  "q": "in:inbox after:2026/3/26 -category:promotions -category:social",
  "maxResults": 20
}'

# 2. Sent mail scan (what was already handled?)
gws gmail users messages list --params '{
  "userId": "me",
  "q": "in:sent after:2026/3/26",
  "maxResults": 15
}'

# 3. Read each message's metadata
gws gmail users messages get --params '{
  "userId": "me",
  "id": "MSG_ID",
  "format": "metadata",
  "metadataHeaders": ["From", "To", "Subject", "Date"]
}'

# 4. Read full body when needed
gws gmail users messages get --params '{
  "userId": "me",
  "id": "MSG_ID",
  "format": "full"
}'

# 5. Today's calendar
gws calendar events list --params '{
  "calendarId": "primary",
  "timeMin": "2026-03-27T00:00:00+00:00",
  "timeMax": "2026-03-27T23:59:59+00:00",
  "singleEvents": true,
  "orderBy": "startTime"
}'
```

All of this runs in ~3-5 seconds total. The AI parses JSON, cross-references with project management tools, and produces a prioritized brief.

---

## The Migration (2 days)

### Timeline

**Day 1:** Infrastructure restructure
1. Installed gws via Homebrew
2. Created a dedicated GCP project via `gws auth setup`
3. Authenticated via `gws auth login` (browser OAuth flow)
4. Granted 10 scopes (Gmail modify, Calendar, Drive, Sheets, Docs, Presentations, Tasks)
5. Tested basic queries — worked immediately
6. **Decision:** gws replaces Composio Google MCP as primary

**Day 2:** Full migration
1. Updated all 5 command files to use `gws` as primary, Composio MCP as fallback
2. Updated all 4 agent definitions
3. Documented the known quirk (see below)
4. Total migration: **~30 minutes** for 9 files

### What Got Better

| Before (Composio MCP) | After (gws CLI) |
|------------------------|------------------|
| Auth expires unpredictably | Token auto-refreshes locally |
| HTTP round-trip to proxy server | Direct Google API call |
| Opaque errors from proxy | Clear exit codes (0-5) |
| Token in third-party's infrastructure | AES-256-GCM encrypted, key in OS keyring |
| Composio outage = no Google access | Works offline (cached tokens) |
| MCP tool schema must be loaded first | Just `gws gmail ...` in bash |

### What I Kept Composio For

- **Secondary account** (different org) — still needs Composio because gws currently supports one account
- **Chat and project management tools** — no gws equivalent, MCP servers handle these

---

## Known Quirks & Workarounds

### 1. Keyring Backend Output

gws prints `Using keyring backend: keyring` to stdout before JSON output. When piping to `jq` or having an AI parse the response, this line must be stripped.

**Workaround:** Documented in all workflow files. The AI knows to expect and strip this line. Example note in commands:

> *Note: gws outputs a "Using keyring backend: keyring" line before JSON — strip it when piping to parsers.*

### 2. Base64-Encoded Email Bodies

Gmail API returns email bodies as base64-encoded strings nested in `payload.parts`. Not a gws issue — it's the Gmail API itself. But since gws gives you raw API responses, you need to handle decoding.

**Workaround:** The AI handles base64 decoding in its parsing step. Works reliably.

### 3. No Multi-Account Profiles (Yet)

This is the biggest gap for my use case. I run operations across two Google Workspace domains.

**Current workaround:** gws for primary account, Composio MCP for secondary.
**Ideal:** Named profiles with separate credentials per account.

---

## Performance in Practice

### Daily Usage (4+ weeks in production)

- **~50-80 gws calls per session** (morning brief + parallel sweep + ad-hoc queries)
- **Zero auth failures** since initial setup (10 days running)
- **Zero downtime** — no dependency on external service availability
- **Latency:** Individual calls complete in <1s (Gmail list), <2s (full message read), <1s (calendar events)
- **Auto-pagination:** `--page-all` used for Gmail searches that span weeks — handles it cleanly

### Session Metrics

A typical `/morning` session hits gws approximately:
- 2 Gmail list queries (inbox + sent)
- 10-15 Gmail get queries (message metadata + full reads)
- 1 Calendar list query
- Total: ~15-20 gws calls in ~10 seconds

A parallel sweep (5 agents):
- Gmail agent: 5-10 list + 20-30 get queries
- Calendar agent: 2-3 list queries
- Total: ~30-40 gws calls across parallel agents in ~15 seconds

### Reliability

| Metric | Value |
|--------|-------|
| Days in production | 10 |
| Auth failures | 0 |
| API errors (4xx/5xx) | 0 (that weren't user error) |
| Token refreshes | Transparent (never noticed) |
| Total gws invocations (est.) | 500-800+ |

---

## Why gws Over Alternatives

I evaluated several options before landing on gws:

| Option | Verdict |
|--------|---------|
| **Google Cloud SDK (gcloud)** | Too heavy, designed for infra, poor Workspace coverage |
| **Composio MCP** | Works but adds latency, auth fragility, third-party dependency |
| **Claude.ai built-in Gmail/Calendar** | Read-only in practice, auth expires on Claude's side, no control |
| **Custom scripts (Python + google-auth)** | Maintenance burden, reinventing the wheel |
| **gws CLI** | Single binary, full API coverage, structured output, encrypted creds |

The killer feature for AI-agent workflows: **gws exposes the raw Google API with structured JSON output**. The AI doesn't need a wrapper or adapter — it constructs the `--params` JSON directly and parses the response. It's the thinnest possible layer between "I need this data" and "here it is."

---

## Feature Requests for Multi-Account Workflows

Based on 10 days of production use:

### 1. Named Profiles (High Priority)
```bash
gws auth login --profile secondary  # Separate OAuth flow
gws --profile secondary gmail users messages list ...
```
Separate `~/.config/gws/profiles/<name>/` directories with independent credentials, tokens, and GCP projects.

### 2. Profile-Aware Env Var
```bash
export GWS_PROFILE=secondary
gws gmail users messages list ...  # Uses secondary credentials
```

### 3. Cross-Account Workflows
```bash
gws workflow +cross-account-inbox \
  --profiles agency,secondary \
  --query "in:inbox after:2026/3/26"
```

### 4. Account Listing
```bash
gws auth list  # Show all configured profiles with status
# agency       user@agency.com         token valid
# secondary    user@other-org.com      token expired
```

---

## Conclusion

gws replaced a fragile MCP-proxy-to-Google-API chain with a single, reliable CLI binary. It eliminated auth failures, reduced latency, and kept credentials local. For AI-agent workflows where an LLM constructs API calls programmatically, gws's thin-layer design is ideal — raw JSON in, raw JSON out, no abstractions in the way.

The main gap is multi-account support. Once profiles land, I can drop the last Composio dependency for Google Workspace entirely.

---

*Built with gws 0.16.0 on macOS. AI orchestration via Claude Code (Anthropic). All metrics from real production usage.*
