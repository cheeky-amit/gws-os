---
name: gws-morning
description: Full morning brief across all GWS accounts — priorities, calendar, and recommended actions
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

# Strip keyring backend output
gws_clean() {
    GOOGLE_WORKSPACE_CLI_CONFIG_DIR="$PROFILES_DIR/$1" gws "${@:2}" 2>&1 | grep -v '^Using keyring backend:'
}

echo "=== GWS Morning Brief ==="
echo "Date: $(date '+%A, %B %d %Y')"
echo ""

# --- Email scan across all accounts ---
for PROFILE in $(jq -r '.accounts[].gws_profile' "$REGISTRY"); do
    SCAN_WINDOW=$(jq -r --arg p "$PROFILE" '.accounts[] | select(.gws_profile==$p) | .scan_window // "24h"' "$REGISTRY")
    LABEL=$(jq -r --arg p "$PROFILE" '.accounts[] | select(.gws_profile==$p) | .label' "$REGISTRY")
    EMAIL=$(jq -r --arg p "$PROFILE" '.accounts[] | select(.gws_profile==$p) | .email' "$REGISTRY")

    echo "=== Inbox: $LABEL ($EMAIL) [window: $SCAN_WINDOW] ==="

    # Unread messages (headers only)
    MESSAGES=$(gws_clean "$PROFILE" gmail users messages list \
        --params "{\"userId\":\"me\",\"maxResults\":20,\"q\":\"is:unread newer_than:${SCAN_WINDOW} -category:promotions -category:social\"}" \
        --format json) || {
        echo "WARNING: Failed to fetch inbox for $LABEL — skipping"
        continue
    }
    echo "$MESSAGES"

    MSG_IDS=$(echo "$MESSAGES" | jq -r '.messages[]?.id // empty' 2>/dev/null)
    if [[ -n "$MSG_IDS" ]]; then
        echo "--- Headers ---"
        for MSG_ID in $MSG_IDS; do
            gws_clean "$PROFILE" gmail users messages get \
                --params "{\"userId\":\"me\",\"id\":\"$MSG_ID\",\"format\":\"metadata\",\"metadataHeaders\":[\"Subject\",\"From\",\"Date\"]}" \
                --format json || true
        done
    else
        echo "  No unread messages."
    fi

    # Sent messages (what was already handled?)
    echo "--- Sent (last $SCAN_WINDOW) ---"
    gws_clean "$PROFILE" gmail users messages list \
        --params "{\"userId\":\"me\",\"maxResults\":10,\"q\":\"in:sent newer_than:${SCAN_WINDOW}\"}" \
        --format json || echo "  (failed to fetch sent)"
    echo ""
done

# --- Calendar for today ---
NOW_START=$(date -u +"%Y-%m-%dT00:00:00Z")
NOW_END=$(date -u -v+1d +"%Y-%m-%dT00:00:00Z" 2>/dev/null || date -u -d "+1 day" +"%Y-%m-%dT00:00:00Z")

for PROFILE in $(jq -r '.accounts[].gws_profile' "$REGISTRY"); do
    LABEL=$(jq -r --arg p "$PROFILE" '.accounts[] | select(.gws_profile==$p) | .label' "$REGISTRY")
    echo "=== Calendar: $LABEL ==="
    gws_clean "$PROFILE" calendar events list \
        --params "{\"calendarId\":\"primary\",\"timeMin\":\"$NOW_START\",\"timeMax\":\"$NOW_END\",\"singleEvents\":true,\"orderBy\":\"startTime\"}" \
        --format json || echo "  (failed to fetch calendar)"
    echo ""
done

# --- Memory context ---
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

echo "=== Account Personas ==="
for PERSONA_FILE in "$GWS_OS_DIR"/accounts/personas/*.md; do
    if [[ -f "$PERSONA_FILE" && "$(basename "$PERSONA_FILE")" != "example.md" ]]; then
        echo "--- $(basename "$PERSONA_FILE") ---"
        cat "$PERSONA_FILE"
        echo ""
    fi
done
```

## Instructions

You are the GWS Morning skill — the flagship daily brief. Using the email, calendar, and memory context above:

### Step 1: What Happened
Summarize what was already handled (sent emails) so the user doesn't re-process old items.

### Step 2: Priority Ranking
Rank all unread emails across accounts using this sort order:
1. **VIP status** (binary — VIPs from personas always on top)
2. **Topic relevance** (recognized topics from contact nodes rank higher)
3. **Trust level** (contacts with higher trust = more context available)
4. **Recency** (newer first as tiebreaker)

### Step 3: Today's Calendar
Show today's schedule across all accounts. Flag:
- Meetings with known contacts (pull context from memory nodes)
- Back-to-back conflicts
- Meetings requiring prep

### Step 4: Recommended Actions
For each priority item, suggest a concrete action:
- Draft a reply (specify which account)
- Schedule a follow-up
- Archive/dismiss
- Flag for later

### Step 5: Execute (with confirmation)
- **Archive**: Execute immediately if trust=automate for that contact+action
- **Reply/Send/Schedule**: **Always wait for user confirmation** (mandatory gate)
- After each action, update memory nodes (contact last_contact, observations count)

### Step 6: Update Memory
- Create/update contact nodes for new senders
- Update observation counts and last_contact dates
- Log all actions to `memory/actions/` JSONL files
