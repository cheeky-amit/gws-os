---
name: gws-reply
description: Context-aware reply from the right account — uses memory, persona, and trust to draft and send
---

```bash
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/gws-common.sh"
gws_init

echo "=== GWS Reply ==="
echo ""

# Load account info
echo "=== Configured Accounts ==="
print_accounts
echo ""

# Load personas
echo "=== Personas ==="
print_personas

# Load contacts for context
echo "=== Known Contacts ==="
print_contacts
```

## Instructions

You are the GWS Reply skill. The user wants to reply to an email. Your job is to draft and send a context-aware reply from the correct account.

### Step 1: Identify the Email
Ask the user which email to reply to, or accept a reference from a previous triage/morning session (message ID, subject line, or sender name).

### Step 2: Fetch the Thread
Read the full email thread to understand context:
```bash
gws_clean "{profile}" gmail users messages get \
    --params '{"userId":"me","id":"{msg_id}","format":"full"}' \
    --format json
```

For threads, also fetch the thread:
```bash
gws_clean "{profile}" gmail users threads get \
    --params '{"userId":"me","id":"{thread_id}","format":"metadata"}' \
    --format json
```

### Step 3: Build Context
- Read the contact node from `memory/contacts/` for the sender
- Check trust level for `reply` action on this contact
- Load the account persona for tone, sign-off, and style
- Check topic nodes for relevant patterns

### Step 4: Draft the Reply
Based on trust level:
- **observe**: Don't draft — just show the email and let the user write
- **suggest**: Suggest key points to include, let user write
- **assist/automate**: Draft a full reply matching the persona's tone

The draft should:
- Match the persona's tone and sign-off
- Reference relevant context from memory
- Be appropriately formal/casual based on the contact's communication pattern
- Include any relevant action items or follow-ups

### Step 5: User Confirms Before Send (MANDATORY)
Show the drafted reply and ask for confirmation. The user may:
- **Approve as-is** → send it
- **Edit** → apply their changes, then send (note: this is a trust demotion signal)
- **Reject** → don't send (trust demotion signal)

### Step 6: Send from Correct Account
Always reply from the account that received the email:
```bash
# Encode the reply as base64url RFC 2822
# The raw field must contain: From, To, Subject (with Re:), In-Reply-To, References headers + body
gws_clean "{profile}" gmail users messages send \
    --params '{"userId":"me"}' \
    --json '{"raw":"{base64url_encoded_message}","threadId":"{thread_id}"}'
```

### Step 7: Update Memory
- Update contact node: increment observations, update last_contact
- Log the action to `memory/actions/reply.jsonl`
- If user edited the draft: note the edit (trust signal)
- If user rejected: note the rejection (trust demotion)
- Update streak counters on the contact node
