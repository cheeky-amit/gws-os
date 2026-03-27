---
name: gws-search
description: Cross-account, cross-service search — find emails, events, and files with natural language
---

```bash
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/gws-common.sh"
gws_init

echo "=== GWS Search ==="
echo ""

# Show available accounts and services
echo "Accounts:"
print_accounts
echo ""
echo "Services: gmail, calendar, drive, sheets, docs, tasks"
echo ""

# Load contacts for resolving names to emails
echo "=== Known Contacts ==="
print_contacts
```

## Instructions

You are the GWS Search skill. The user wants to find something across their Google Workspace accounts.

### Step 1: Parse the Query
Accept a natural language query and extract:
- **Target service**: email, calendar, drive, or "all"
- **Target accounts**: specific account or "all"
- **Time range**: if mentioned ("last week", "in March", etc.)
- **People**: resolve names to email addresses using contact nodes
- **Keywords**: search terms

Examples:
- "find the report Jane sent last week" → Gmail, all accounts, from:jane@acme.com, newer_than:7d
- "what meetings do I have with the Acme team?" → Calendar, all accounts, attendee search
- "find the Q1 spreadsheet" → Drive, all accounts, name contains "Q1"

### Step 2: Execute Searches
Run the appropriate `gws` commands across relevant accounts:

**Gmail:**
```bash
gws_clean "{profile}" gmail users messages list \
    --params '{"userId":"me","maxResults":20,"q":"{gmail_query}"}' \
    --format json
```

**Calendar:**
```bash
gws_clean "{profile}" calendar events list \
    --params '{"calendarId":"primary","q":"{search_term}","timeMin":"{start}","timeMax":"{end}","singleEvents":true}' \
    --format json
```

**Drive:**
```bash
gws_clean "{profile}" drive files list \
    --params '{"q":"name contains '\''{term}'\''","fields":"files(id,name,mimeType,modifiedTime,webViewLink)"}' \
    --format json
```

### Step 3: Merge and Deduplicate
- Combine results from all accounts
- Remove duplicates (same thread appearing in multiple accounts)
- Group by service type

### Step 4: Present Results
```
RESULTS (12 found across 2 accounts)

📧 Email (8)
  [business] "Q1 Report Review" — from Jane Smith — Mar 25
  [business] "Q1 Numbers Updated" — from Jane Smith — Mar 20
  ...

📅 Calendar (2)
  [business] "Q1 Review Meeting" — Mar 28 2:00 PM — with Jane Smith
  ...

📁 Drive (2)
  [business] "Q1-Report-Final.xlsx" — modified Mar 24
  [personal] "Q1-Notes.gdoc" — modified Mar 22
```

### Step 5: Drill Down
Offer to read any result in detail:
- Email: fetch full body
- Calendar: show full event details + attendees
- Drive: show file metadata + sharing info
