---
name: gws-morning
description: Full morning brief across all GWS accounts — priorities, calendar, and recommended actions
---

```bash
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/gws-common.sh"
gws_init

echo "=== GWS Morning Brief ==="
echo "Date: $(date '+%A, %B %d %Y')"
echo ""

# --- Email scan across all accounts ---
for PROFILE in $(get_profiles); do
    SCAN_WINDOW=$(get_account_field "$PROFILE" scan_window)
    SCAN_WINDOW="${SCAN_WINDOW:-24h}"
    LABEL=$(get_account_field "$PROFILE" label)
    EMAIL=$(get_account_field "$PROFILE" email)

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

for PROFILE in $(get_profiles); do
    LABEL=$(get_account_field "$PROFILE" label)
    echo "=== Calendar: $LABEL ==="
    gws_clean "$PROFILE" calendar events list \
        --params "{\"calendarId\":\"primary\",\"timeMin\":\"$NOW_START\",\"timeMax\":\"$NOW_END\",\"singleEvents\":true,\"orderBy\":\"startTime\"}" \
        --format json || echo "  (failed to fetch calendar)"
    echo ""
done

# --- Memory context ---
echo "=== Known Contacts ==="
print_contacts

echo "=== Account Personas ==="
print_personas
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
