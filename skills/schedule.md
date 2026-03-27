---
name: gws-schedule
description: Cross-calendar scheduling — find optimal slots respecting all account personas and constraints
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

echo "=== GWS Schedule ==="
echo ""

# Pull events from all calendars (next 14 days)
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
END=$(date -u -v+14d +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -d "+14 days" +"%Y-%m-%dT%H:%M:%SZ")

for PROFILE in $(jq -r '.accounts[].gws_profile' "$REGISTRY"); do
    LABEL=$(jq -r --arg p "$PROFILE" '.accounts[] | select(.gws_profile==$p) | .label' "$REGISTRY")
    echo "=== Calendar: $LABEL ==="
    gws_clean "$PROFILE" calendar events list \
        --params "{\"calendarId\":\"primary\",\"timeMin\":\"$NOW\",\"timeMax\":\"$END\",\"singleEvents\":true,\"orderBy\":\"startTime\"}" \
        --format json || echo "  (failed to fetch calendar)"
    echo ""
done

# Load personas for scheduling rules
echo "=== Persona Calendar Rules ==="
for PERSONA_FILE in "$GWS_OS_DIR"/accounts/personas/*.md; do
    if [[ -f "$PERSONA_FILE" && "$(basename "$PERSONA_FILE")" != "example.md" ]]; then
        echo "--- $(basename "$PERSONA_FILE") ---"
        cat "$PERSONA_FILE"
        echo ""
    fi
done

# Load scheduling preferences
PLAN_PREFS="$GWS_OS_DIR/memory/topics/scheduling-preferences.md"
if [[ -f "$PLAN_PREFS" ]]; then
    echo "=== Learned Scheduling Preferences ==="
    cat "$PLAN_PREFS"
    echo ""
fi

# Load contacts (for attendee context)
echo "=== Known Contacts ==="
if ls "$GWS_OS_DIR"/memory/contacts/*.md &>/dev/null; then
    for CONTACT_FILE in "$GWS_OS_DIR"/memory/contacts/*.md; do
        echo "--- $(basename "$CONTACT_FILE") ---"
        head -15 "$CONTACT_FILE"
        echo ""
    done
else
    echo "  No contacts in memory yet."
fi
```

## Instructions

You are the GWS Schedule skill. The user wants to schedule a meeting or event.

### Step 1: Understand the Request
Ask (or infer from context) what needs to be scheduled:
- Meeting title/purpose
- Required attendees (check contact nodes for email addresses)
- Duration
- Preferred time range (or "anytime this week")
- Which account should own the event

### Step 2: Find Available Slots
Using the calendar data above, identify free slots that:
- Don't overlap with existing events on ANY account calendar
- Respect persona rules (business hours, no-meeting blocks, half days)
- Respect learned scheduling preferences (buffer rules, location rules)
- Have appropriate buffers before/after neighboring events

### Step 3: Score and Rank Slots
Present the top 2-3 slots with reasoning:

```
Option 1: Tuesday 2:00-2:30 PM ★★★
  ✓ 30min buffer after previous meeting
  ✓ Within business hours
  ✓ No conflicts on any calendar

Option 2: Wednesday 10:00-10:30 AM ★★
  ✓ Clean morning slot
  ! Followed by another meeting at 10:45 (tight)

Option 3: Thursday 4:00-4:30 PM ★
  ✓ Free slot
  ! Late in the day (energy consideration)
  ! Friday is a half day — no follow-up buffer
```

### Step 4: User Confirms (MANDATORY)
Present the chosen slot and full event details. Wait for explicit confirmation before creating.

### Step 5: Create the Event
```bash
gws_clean "{profile}" calendar events insert \
    --params '{"calendarId":"primary"}' \
    --json '{
        "summary": "{title}",
        "start": {"dateTime": "{start_iso}", "timeZone": "{tz}"},
        "end": {"dateTime": "{end_iso}", "timeZone": "{tz}"},
        "attendees": [{"email": "{attendee}"}],
        "description": "{description}"
    }'
```

### Step 6: Update Memory
- Log the schedule action to `memory/actions/schedule.jsonl`
- Update contact nodes for attendees (last_contact, observations)
- Update scheduling preferences if the user provided new rules
