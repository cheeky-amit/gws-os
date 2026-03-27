---
name: gws-reply
description: Context-aware reply from the right account — uses memory, persona, and trust to draft and send
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

echo "=== GWS Reply ==="
echo ""

# Load account info
echo "=== Configured Accounts ==="
jq -r '.accounts[] | "  \(.id): \(.email) (\(.label))"' "$REGISTRY"
echo ""

# Load personas
echo "=== Personas ==="
for PERSONA_FILE in "$GWS_OS_DIR"/accounts/personas/*.md; do
    if [[ -f "$PERSONA_FILE" && "$(basename "$PERSONA_FILE")" != "example.md" ]]; then
        echo "--- $(basename "$PERSONA_FILE") ---"
        cat "$PERSONA_FILE"
        echo ""
    fi
done

# Load contacts for context
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
