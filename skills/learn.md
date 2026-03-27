---
name: gws-learn
description: Transparency and control — see what the system knows, adjust trust levels, undo automated actions
---

```bash
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/gws-common.sh"
gws_init

echo "=== GWS Learn — What I Know ==="
echo ""

echo "Memory Stats:"
print_memory_summary
echo ""

# All contacts with trust levels
echo "=== All Contacts ==="
print_contacts

# All topics with patterns
echo "=== All Topics ==="
print_topics

# Global trust defaults
if [[ -f "$GWS_MEMORY_DIR/trust-levels.json" ]]; then
    echo "=== Global Trust Defaults ==="
    cat "$GWS_MEMORY_DIR/trust-levels.json"
    echo ""
fi

# Today's automate log
DATE=$(date +"%Y-%m-%d")
AUTO_LOG="$GWS_MEMORY_DIR/actions/automate-log-${DATE}.jsonl"
if [[ -f "$AUTO_LOG" ]]; then
    echo "=== Today's Automated Actions ==="
    cat "$AUTO_LOG"
    echo ""
else
    echo "=== Today's Automated Actions ==="
    echo "  None."
    echo ""
fi

# Scheduling preferences
PLAN_PREFS="$GWS_MEMORY_DIR/topics/scheduling-preferences.md"
if [[ -f "$PLAN_PREFS" ]]; then
    echo "=== Scheduling Preferences ==="
    cat "$PLAN_PREFS"
    echo ""
fi
```

## Instructions

You are the GWS Learn skill — the transparency and control layer. Show the user everything the system has learned, and let them adjust it.

### Mode 1: Overview (default)
Present a clear summary of the system's knowledge:

```
GWS OS KNOWLEDGE BASE
  12 contacts | 5 topics | 847 actions logged

TOP CONTACTS (by observations)
  Jane Smith (jane@acme.com) — 18 observations
    Trust: reply=assist, archive=automate, schedule=suggest
    Topics: quarterly-reports, performance-marketing
    Streak: reply_streak=3 (2 more to promote to automate)

  Bob Jones (bob@example.com) — 8 observations
    Trust: reply=suggest, archive=observe
    Topics: project-updates

LEARNED PATTERNS
  "Quarterly report emails → schedule review call within 48h"
    Confidence: 0.6 (12/20 observations)
    Contacts: Jane Smith, team@acme.com

TRUST SUMMARY
  automate: 3 contact+action pairs
  assist: 5 contact+action pairs
  suggest: 8 contact+action pairs
  observe: 14 contact+action pairs (default)
```

### Mode 2: Undo Automated Actions
If the user asks to undo or review automated actions:
1. Show today's automate log with details
2. For each action, show the reverse command
3. Let the user select which to undo
4. Execute the reverse command
5. **Demote trust** for that contact+action pair (automate → assist)
6. Update the contact node

### Mode 3: Adjust Trust
If the user wants to change trust levels:
- "Trust Jane for replies" → set reply trust to assist/automate on Jane's contact node
- "Don't auto-archive from Bob" → set archive trust to observe on Bob's contact node
- "Reset all trust for Jane" → set all trust levels to observe on Jane's contact node
- Update the contact node directly

### Mode 4: Correct Patterns
If the user says a pattern is wrong:
- Update or delete the pattern field in the topic node
- Reset confidence to 0 if the pattern was completely wrong
- Note the correction in the topic node

### Mode 5: Delete Knowledge
If the user wants to forget something:
- Delete a specific contact node
- Delete a specific topic node
- Clear all action logs for a contact
- Confirm before any deletion

### Important
- This skill is read-heavy — most operations just display information
- Write operations (undo, trust adjust, corrections) always require user confirmation
- Trust changes made here are manual overrides — they take effect immediately
- All changes are logged to `memory/actions/learn.jsonl`
