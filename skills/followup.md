---
name: gws-followup
description: Track threads awaiting response and surface overdue follow-ups across accounts
---

```bash
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/gws-common.sh"
gws_init

echo "=== GWS Follow-Up Tracker ==="
echo ""

# Scan sent mail from all accounts (last 7 days)
for PROFILE in $(get_profiles); do
    LABEL=$(get_account_field "$PROFILE" label)
    EMAIL=$(get_account_field "$PROFILE" email)

    echo "=== Sent Mail: $LABEL ($EMAIL) ==="

    # Sent in last 7 days
    SENT=$(gws_clean "$PROFILE" gmail users messages list \
        --params "{\"userId\":\"me\",\"maxResults\":30,\"q\":\"in:sent newer_than:7d\"}" \
        --format json) || {
        echo "WARNING: Failed to fetch sent for $LABEL — skipping"
        continue
    }

    SENT_IDS=$(echo "$SENT" | jq -r '.messages[]?.id // empty' 2>/dev/null)
    if [[ -n "$SENT_IDS" ]]; then
        echo "--- Sent Headers ---"
        for MSG_ID in $SENT_IDS; do
            gws_clean "$PROFILE" gmail users messages get \
                --params "{\"userId\":\"me\",\"id\":\"$MSG_ID\",\"format\":\"metadata\",\"metadataHeaders\":[\"Subject\",\"To\",\"Date\",\"In-Reply-To\"]}" \
                --format json || true
        done
    else
        echo "  No sent messages in last 7 days."
    fi
    echo ""
done

# Load contacts for expected response patterns
echo "=== Known Contacts ==="
print_contacts
```

## Instructions

You are the GWS Follow-Up skill. Your job is to find threads where you sent a message and haven't received a response.

### Step 1: Identify Pending Threads
For each sent email, check if the thread has a newer reply from the recipient. A thread is "pending follow-up" if:
- You sent the last message in the thread
- No reply has been received
- It's been more than the expected response time (from contact node patterns, or 48h default)

### Step 2: Rank by Importance
Sort pending follow-ups by:
1. **VIP contacts** (from personas) — always on top
2. **Overdue duration** (days past expected response time)
3. **Topic importance** (from topic nodes if available)

### Step 3: Present Follow-Up Dashboard

```
OVERDUE (2)
  ⏰ [business] Jane Smith — "Q1 Report Review" — sent 4 days ago
     Expected response: 48h | Overdue by: 2 days
     Suggestion: Send a gentle nudge

  ⏰ [business] Team — "Budget approval needed" — sent 3 days ago
     Expected response: 24h | Overdue by: 2 days
     Suggestion: Follow up with deadline

PENDING (3)
  ⌛ [personal] Bank — "Account inquiry" — sent 1 day ago
     Expected response: 48h | Due in: 1 day

  ...
```

### Step 4: Suggest Nudge Drafts
For overdue items, offer to draft a follow-up nudge. Use the account persona for tone. Keep nudges short and professional.

### Step 5: Execute (with confirmation)
- **Nudge drafts**: Show draft, **wait for user confirmation before sending** (mandatory gate)
- After sending, update contact node (log the follow-up action)
- Log to `memory/actions/followup.jsonl`
