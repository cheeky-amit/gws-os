---
name: gws-brief
description: Pre-meeting intelligence — assemble context on attendees from email, calendar, and memory
---

```bash
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/gws-common.sh"
gws_init

echo "=== GWS Brief ==="
echo ""

# Pull upcoming events (next 24h) to find the meeting
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
END=$(date -u -v+1d +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -d "+1 day" +"%Y-%m-%dT%H:%M:%SZ")

for PROFILE in $(get_profiles); do
    LABEL=$(get_account_field "$PROFILE" label)
    echo "=== Upcoming: $LABEL ==="
    gws_clean "$PROFILE" calendar events list \
        --params "{\"calendarId\":\"primary\",\"timeMin\":\"$NOW\",\"timeMax\":\"$END\",\"singleEvents\":true,\"orderBy\":\"startTime\"}" \
        --format json || echo "  (failed to fetch calendar)"
    echo ""
done

# Load contacts
echo "=== Known Contacts ==="
print_contacts

# Load topics
echo "=== Known Topics ==="
print_topics
```

## Instructions

You are the GWS Brief skill. The user has an upcoming meeting and needs a context brief.

### Step 1: Identify the Meeting
Ask which meeting to brief on, or select the next upcoming meeting from the calendar data above.

### Step 2: Look Up Attendees
For each attendee:
- Check `memory/contacts/` for existing contact nodes
- If known: pull their topics, communication patterns, trust levels, last interaction
- If unknown: note as "new contact — no prior history"

### Step 3: Pull Recent Email Threads
For each known attendee, search for recent email threads across all accounts:
```bash
gws_clean "{profile}" gmail users messages list \
    --params '{"userId":"me","maxResults":10,"q":"from:{attendee_email} OR to:{attendee_email}"}' \
    --format json
```

Fetch headers for the most recent threads to understand what's been discussed.

### Step 4: Compile the Brief
Present a structured 1-page brief:

```
MEETING BRIEF: {meeting title}
Time: {time} | Duration: {duration} | Calendar: {account}

ATTENDEES
  ★ Jane Smith (jane@acme.com) — 18 prior interactions
    Last contact: 3 days ago (replied to Q1 report thread)
    Topics: quarterly-reports, performance-marketing
    Pattern: formal, expects quick turnarounds
    Trust: reply=assist, schedule=suggest

  ? New Person (new@unknown.com) — no prior history

RECENT THREADS
  1. "Q1 Report Review" (3 days ago) — awaiting your response
  2. "Budget reallocation" (1 week ago) — resolved

OPEN ACTION ITEMS
  - Follow up on Q1 report (from triage 3 days ago)

SUGGESTED PREP
  - Review the Q1 report before the call
  - Prepare updated numbers for discussion
```

### Step 5: Update Memory
- Create contact nodes for any new attendees discovered
- Update last_contact on existing contacts
- Log the brief action to `memory/actions/brief.jsonl`
