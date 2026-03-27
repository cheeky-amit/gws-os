---
name: gws-weekly
description: Weekly review — summarize actions, patterns learned, trust changes, and overdue follow-ups
---

```bash
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/gws-common.sh"
gws_init

echo "=== GWS Weekly Review ==="
echo "Week ending: $(date '+%A, %B %d %Y')"
echo ""

# Load all action logs from the past 7 days
echo "=== Action Logs (Last 7 Days) ==="
CUTOFF=$(date -u -v-7d +"%Y-%m-%d" 2>/dev/null || date -u -d "-7 days" +"%Y-%m-%d")
for ACTION_FILE in "$GWS_MEMORY_DIR"/actions/*.jsonl; do
    if [[ -f "$ACTION_FILE" ]]; then
        BASENAME=$(basename "$ACTION_FILE")
        # Filter to last 7 days
        RECENT=$(awk -v cutoff="$CUTOFF" '$0 ~ cutoff || $0 > cutoff' "$ACTION_FILE" 2>/dev/null | tail -50)
        if [[ -n "$RECENT" ]]; then
            echo "--- $BASENAME ---"
            echo "$RECENT"
            echo ""
        fi
    fi
done

# Load all contact nodes
echo "=== Contact Nodes ==="
print_contacts

# Load all topic nodes
echo "=== Topic Nodes ==="
print_topics

# Load automate logs
echo "=== Automated Actions This Week ==="
for i in $(seq 0 6); do
    DATE=$(date -v-${i}d +"%Y-%m-%d" 2>/dev/null || date -d "-${i} days" +"%Y-%m-%d")
    LOG="$GWS_MEMORY_DIR/actions/automate-log-${DATE}.jsonl"
    if [[ -f "$LOG" ]]; then
        echo "--- $DATE ---"
        cat "$LOG"
        echo ""
    fi
done
```

## Instructions

You are the GWS Weekly skill. Present a weekly review of the user's GWS OS activity and learning progress.

### Section 1: Activity Summary
Summarize what happened this week:
- Total actions logged (replies, archives, schedules, etc.)
- Actions per account
- Busiest day / quietest day
- Most-contacted people

### Section 2: New Patterns Detected
Review topic nodes for new or updated patterns:
- Any topic that crossed the 5-observation threshold this week
- Any pattern field that was newly written by pattern-detect.sh
- Emerging (action, contact) sequences that are becoming consistent

### Section 3: Trust Level Changes
Report any trust level changes on contact nodes:
- Promotions (observe→suggest, suggest→assist, assist→automate)
- Demotions (from user overrides/edits/rejections)
- Contacts approaching promotion thresholds (streak at 4/5, etc.)

### Section 4: Automated Actions Report
If any actions ran at `automate` trust level:
- List what was automated (archives, etc.)
- Confirm they were all logged with reverse commands
- Flag any that might need review

### Section 5: Overdue Follow-Ups
Surface threads from `/gws followup` that are still pending:
- How many threads are awaiting response
- Which are most overdue

### Section 6: Recommendations
Based on the week's patterns, suggest:
- Contacts that might be ready for trust promotion
- Topics that should be watched more closely
- Scheduling preferences that could be formalized
- Any memory cleanup needed (stale contacts, outdated topics)
