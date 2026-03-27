---
name: gws-triage
description: Triage emails across GWS accounts — categorize, prioritize, and act on unread messages
---

```bash
# Verify dependencies
command -v gws >/dev/null 2>&1 || { echo "ERROR: gws not installed. Run 'bash setup' first"; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "ERROR: jq required. Run: brew install jq"; exit 1; }

GWS_OS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGISTRY="$GWS_OS_DIR/accounts/registry.json"
PROFILES_DIR="$HOME/.config/gws-profiles"

if [[ ! -f "$REGISTRY" ]]; then
    echo "ERROR: No accounts configured. Run 'bash setup' first."
    exit 1
fi

echo "=== GWS Triage ==="
echo ""

# Helper: strip "Using keyring backend: keyring" line that gws prints before JSON
gws_clean() {
    GOOGLE_WORKSPACE_CLI_CONFIG_DIR="$PROFILES_DIR/$1" gws "${@:2}" 2>&1 | grep -v '^Using keyring backend:'
}

# Pull unread HEADERS ONLY from each account (lightweight preamble)
for PROFILE in $(jq -r '.accounts[].gws_profile' "$REGISTRY"); do
    ACCOUNT_ID="$PROFILE"
    SCAN_WINDOW=$(jq -r --arg p "$PROFILE" '.accounts[] | select(.gws_profile==$p) | .scan_window // "24h"' "$REGISTRY")
    LABEL=$(jq -r --arg p "$PROFILE" '.accounts[] | select(.gws_profile==$p) | .label' "$REGISTRY")
    EMAIL=$(jq -r --arg p "$PROFILE" '.accounts[] | select(.gws_profile==$p) | .email' "$REGISTRY")

    echo "=== Account: $LABEL ($EMAIL) [window: $SCAN_WINDOW] ==="

    # List unread message IDs (gws_clean strips keyring backend output)
    MESSAGES=$(gws_clean "$PROFILE" gmail users messages list \
        --params "{\"userId\":\"me\",\"maxResults\":20,\"q\":\"is:unread newer_than:${SCAN_WINDOW}\"}" \
        --format json) || {
        echo "WARNING: Failed to fetch messages for $LABEL — skipping"
        continue
    }

    echo "$MESSAGES"

    # For each message, get headers only (Subject, From, Date)
    MSG_IDS=$(echo "$MESSAGES" | jq -r '.messages[]?.id // empty' 2>/dev/null)
    if [[ -z "$MSG_IDS" ]]; then
        echo "  No unread messages."
        continue
    fi

    echo "--- Headers ---"
    for MSG_ID in $MSG_IDS; do
        gws_clean "$PROFILE" gmail users messages get \
            --params "{\"userId\":\"me\",\"id\":\"$MSG_ID\",\"format\":\"metadata\",\"metadataHeaders\":[\"Subject\",\"From\",\"Date\"]}" \
            --format json || echo "  (failed to fetch $MSG_ID)"
    done
    echo ""
done

# Load known contacts for context
echo "=== Known Contacts ==="
if ls "$GWS_OS_DIR"/memory/contacts/*.md &>/dev/null; then
    for CONTACT_FILE in "$GWS_OS_DIR"/memory/contacts/*.md; do
        echo "--- $(basename "$CONTACT_FILE") ---"
        head -20 "$CONTACT_FILE"
        echo ""
    done
else
    echo "  No contacts in memory yet."
fi

# Load persona for each account
echo "=== Account Personas ==="
for PERSONA_FILE in "$GWS_OS_DIR"/accounts/personas/*.md; do
    if [[ -f "$PERSONA_FILE" ]]; then
        echo "--- $(basename "$PERSONA_FILE") ---"
        cat "$PERSONA_FILE"
        echo ""
    fi
done
```

## Instructions

You are the GWS Triage skill. Using the email headers and account context above:

### Step 1: Categorize
For each unread email, categorize as:
- **URGENT** — needs immediate response (VIP sender, time-sensitive content)
- **NEEDS-REPLY** — requires a response but not urgent
- **FYI** — informational, read and move on
- **ARCHIVE** — newsletters, notifications, bulk — safe to archive

### Step 2: Present Dashboard
Show a triage dashboard grouped by category:

```
URGENT (2)
  📧 [business] Jane Smith — "Q1 Report Review" — 2h ago
  📧 [personal] Bank Alert — "Unusual activity" — 30m ago

NEEDS-REPLY (3)
  📧 [business] Team — "Sprint planning agenda" — 5h ago
  ...

FYI (4)
  📧 ...

ARCHIVE (8)
  📧 ...
```

### Step 3: Recommend Actions
For each URGENT and NEEDS-REPLY email, suggest an action:
- Draft a reply (fetch full body first with `gws gmail users messages get`)
- Schedule a follow-up
- Forward to someone
- Just flag for later

### Step 4: Execute (with confirmation)
For actions the user confirms:
- **Archive**: Execute immediately via gws (no confirmation needed if trust=automate for archive)
- **Reply**: Draft the reply, show it, **wait for user confirmation before sending** (mandatory gate)
- **Schedule**: Propose time, **wait for user confirmation** (mandatory gate)

### Step 5: Update Memory
After triage:
- Create/update contact nodes in `memory/contacts/` for any new senders
- Update `last_contact` and `observations` count on existing contacts
- Log actions to `memory/actions/` JSONL files

### Fetching Full Bodies
When you need the full email body to draft a reply or understand context, fetch it:
```bash
GOOGLE_WORKSPACE_CLI_CONFIG_DIR="$HOME/.config/gws-profiles/{profile}" \
    gws gmail users messages get \
    --params '{"userId":"me","id":"{msg_id}","format":"full"}' \
    --format json
```

### Account Routing
When replying, always send from the account that received the email. Use the profile wrapper:
```bash
GOOGLE_WORKSPACE_CLI_CONFIG_DIR="$HOME/.config/gws-profiles/{profile}" \
    gws gmail users messages send \
    --params '{"userId":"me"}' \
    --json '{"raw":"<base64url-encoded-rfc2822>"}'
```
