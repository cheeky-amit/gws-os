#!/usr/bin/env bash
# gws-common.sh — Shared library for all GWS OS skills
# Source this at the top of every skill preamble:
#   source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/gws-common.sh"
#   gws_init

# --- Globals (set by gws_init, or pre-set by tests) ---
GWS_OS_DIR="${GWS_OS_DIR:-}"
GWS_REGISTRY="${GWS_REGISTRY:-}"
GWS_PROFILES_DIR="${GWS_PROFILES_DIR:-$HOME/.config/gws-profiles}"
GWS_MEMORY_DIR="${GWS_MEMORY_DIR:-}"

# --- Core Functions ---

# Initialize GWS OS environment. Call once at the start of every skill preamble.
gws_init() {
    # Resolve GWS OS root (lib/ is one level deep)
    GWS_OS_DIR="$(cd "$(dirname "${BASH_SOURCE[1]:-${BASH_SOURCE[0]}}")/.." && pwd)"
    GWS_REGISTRY="$GWS_OS_DIR/accounts/registry.json"
    GWS_MEMORY_DIR="$GWS_OS_DIR/memory"

    # Validate dependencies
    command -v gws >/dev/null 2>&1 || { echo "ERROR: gws not installed. Run 'bash setup' first"; exit 1; }
    command -v jq >/dev/null 2>&1 || { echo "ERROR: jq required. Run: brew install jq"; exit 1; }

    # Validate registry
    if [[ ! -f "$GWS_REGISTRY" ]]; then
        echo "ERROR: No accounts configured. Run 'bash setup' first."
        exit 1
    fi

    # Ensure memory directories exist
    mkdir -p "$GWS_MEMORY_DIR/contacts" "$GWS_MEMORY_DIR/topics" "$GWS_MEMORY_DIR/actions"
}

# --- gws CLI Wrapper ---

# Call gws with profile isolation, stripping keyring backend output.
# Usage: gws_clean <profile> <gws args...>
gws_clean() {
    local profile="$1"; shift
    GOOGLE_WORKSPACE_CLI_CONFIG_DIR="$GWS_PROFILES_DIR/$profile" gws "$@" 2>&1 | grep -v '^Using keyring backend:'
}

# --- Registry Functions ---

# Get all account profile names (one per line)
get_profiles() {
    jq -r '.accounts[].gws_profile' "$GWS_REGISTRY"
}

# Get a field for a specific profile. Usage: get_account_field <profile> <field>
get_account_field() {
    local profile="$1" field="$2"
    jq -r --arg p "$profile" --arg f "$field" '.accounts[] | select(.gws_profile==$p) | .[$f] // empty' "$GWS_REGISTRY"
}

# Get default account profile name
get_default_profile() {
    jq -r '.default_account' "$GWS_REGISTRY"
}

# Print account summary for display
print_accounts() {
    jq -r '.accounts[] | "  \(.id): \(.email) (\(.label)) [scan: \(.scan_window)]"' "$GWS_REGISTRY"
}

# --- Memory: Contacts ---

# Load all contact nodes as a JSON array (frontmatter only).
# Output: [{"file":"jane-smith.md","email":"jane@acme.com","name":"Jane Smith",...}, ...]
load_contacts() {
    local contacts_dir="$GWS_MEMORY_DIR/contacts"
    local result="[]"

    for contact_file in "$contacts_dir"/*.md; do
        [[ -f "$contact_file" ]] || continue
        [[ "$(basename "$contact_file")" == ".gitkeep" ]] && continue

        # Extract YAML frontmatter between --- markers
        local frontmatter
        frontmatter=$(sed -n '/^---$/,/^---$/p' "$contact_file" | sed '1d;$d')
        [[ -z "$frontmatter" ]] && continue

        # Parse key fields with grep/sed (portable, no python dependency)
        local email name observations last_contact
        email=$(echo "$frontmatter" | grep '^email:' | sed 's/^email: *//')
        name=$(echo "$frontmatter" | grep '^name:' | sed 's/^name: *//')
        observations=$(echo "$frontmatter" | grep '^observations:' | sed 's/^observations: *//')
        last_contact=$(echo "$frontmatter" | grep '^last_contact:' | sed 's/^last_contact: *//')

        result=$(echo "$result" | jq --arg f "$(basename "$contact_file")" \
            --arg e "$email" --arg n "$name" \
            --arg o "${observations:-0}" --arg lc "${last_contact:-}" \
            '. + [{"file":$f,"email":$e,"name":$n,"observations":($o|tonumber),"last_contact":$lc}]')
    done

    echo "$result"
}

# Load a single contact node by email. Returns the full file content or empty.
get_contact() {
    local email="$1"
    local contacts_dir="$GWS_MEMORY_DIR/contacts"

    for contact_file in "$contacts_dir"/*.md; do
        [[ -f "$contact_file" ]] || continue
        if grep -q "^email: *$email" "$contact_file" 2>/dev/null; then
            cat "$contact_file"
            return 0
        fi
    done
    return 1
}

# Get the file path for a contact by email. Returns path or empty.
get_contact_file() {
    local email="$1"
    local contacts_dir="$GWS_MEMORY_DIR/contacts"

    for contact_file in "$contacts_dir"/*.md; do
        [[ -f "$contact_file" ]] || continue
        if grep -q "^email: *$email" "$contact_file" 2>/dev/null; then
            echo "$contact_file"
            return 0
        fi
    done
    return 1
}

# Create a new contact node from template.
# Usage: create_contact <email> <name> <account_id>
create_contact() {
    local email="$1" name="$2" account_id="${3:-}"
    local slug
    slug=$(echo "$name" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')
    local dest="$GWS_MEMORY_DIR/contacts/${slug}.md"

    # Don't overwrite existing
    if [[ -f "$dest" ]]; then
        echo "Contact already exists: $dest"
        return 1
    fi

    # Load global trust defaults
    local trust_defaults='{}'
    if [[ -f "$GWS_MEMORY_DIR/trust-levels.json" ]]; then
        trust_defaults=$(jq -r '.defaults // {}' "$GWS_MEMORY_DIR/trust-levels.json")
    fi

    # Build trust levels YAML from defaults
    local trust_yaml=""
    for action in $(echo "$trust_defaults" | jq -r 'keys[]'); do
        local level
        level=$(echo "$trust_defaults" | jq -r --arg a "$action" '.[$a]')
        trust_yaml="${trust_yaml}  ${action}: ${level}\n"
    done

    local accounts_seen="[]"
    [[ -n "$account_id" ]] && accounts_seen="[$account_id]"

    cat > "$dest" <<EOF
---
email: $email
name: $name
accounts_seen: $accounts_seen
topics: []
communication_pattern: unknown
last_contact: $(date +%Y-%m-%d)
frequency: unknown
observations: 1
trust_levels:
$(echo -e "$trust_yaml")---
EOF

    echo "Created contact: $dest"
}

# Update a field in an existing contact's YAML frontmatter.
# Usage: update_contact <email> <field> <value>
update_contact() {
    local email="$1" field="$2" value="$3"
    local contact_file
    contact_file=$(get_contact_file "$email") || {
        echo "Contact not found: $email"
        return 1
    }

    # Handle numeric fields (increment observations)
    if [[ "$field" == "observations" && "$value" == "+1" ]]; then
        local current
        current=$(grep "^observations:" "$contact_file" | sed 's/^observations: *//')
        value=$((current + 1))
    fi

    # Replace the field in-place (works for simple scalar fields)
    if grep -q "^${field}:" "$contact_file"; then
        sed -i '' "s|^${field}:.*|${field}: ${value}|" "$contact_file"
    else
        # Insert before closing ---
        sed -i '' "/^---$/i\\
${field}: ${value}
" "$contact_file"
    fi
}

# --- Memory: Topics ---

# Load all topic nodes as a JSON array (frontmatter fields).
load_topics() {
    local topics_dir="$GWS_MEMORY_DIR/topics"
    local result="[]"

    for topic_file in "$topics_dir"/*.md; do
        [[ -f "$topic_file" ]] || continue
        [[ "$(basename "$topic_file")" == ".gitkeep" ]] && continue
        [[ "$(basename "$topic_file")" == "scheduling-preferences.md" ]] && continue

        local frontmatter
        frontmatter=$(sed -n '/^---$/,/^---$/p' "$topic_file" | sed '1d;$d')
        [[ -z "$frontmatter" ]] && continue

        local name observations confidence
        name=$(echo "$frontmatter" | grep '^name:' | sed 's/^name: *//')
        observations=$(echo "$frontmatter" | grep '^observations:' | sed 's/^observations: *//')
        confidence=$(echo "$frontmatter" | grep '^confidence:' | sed 's/^confidence: *//')

        result=$(echo "$result" | jq --arg f "$(basename "$topic_file")" \
            --arg n "$name" --arg o "${observations:-0}" --arg c "${confidence:-0}" \
            '. + [{"file":$f,"name":$n,"observations":($o|tonumber),"confidence":($c|tonumber)}]')
    done

    echo "$result"
}

# --- Trust Resolution ---

# Resolve trust level for a contact+action pair.
# Returns: observe, suggest, assist, or automate
# Usage: resolve_trust <contact_email> <action_type>
resolve_trust() {
    local email="$1" action="$2"

    # 1. Check contact node (authoritative)
    local contact_file
    if contact_file=$(get_contact_file "$email" 2>/dev/null); then
        local contact_trust
        contact_trust=$(sed -n '/^trust_levels:/,/^[^ ]/p' "$contact_file" | \
            grep "^  ${action}:" | sed "s/^  ${action}: *//")
        if [[ -n "$contact_trust" ]]; then
            echo "$contact_trust"
            return 0
        fi
    fi

    # 2. Fall back to global defaults
    if [[ -f "$GWS_MEMORY_DIR/trust-levels.json" ]]; then
        local global_trust
        global_trust=$(jq -r --arg a "$action" '.defaults[$a] // "observe"' "$GWS_MEMORY_DIR/trust-levels.json")
        echo "$global_trust"
        return 0
    fi

    # 3. Ultimate fallback
    echo "observe"
}

# --- Action Logging ---

# Log an action and auto-update the contact node.
# Usage: log_action <action> <account_id> <contact_email> [topic]
log_action() {
    local action="$1" account="$2" contact="$3" topic="${4:-}"

    # Log to action JSONL
    local ts
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local entry
    entry=$(jq -cn --arg ts "$ts" --arg action "$action" --arg account "$account" \
        --arg contact "$contact" --arg topic "$topic" \
        '{ts:$ts, action:$action, account:$account, contact:$contact, topic:$topic}')

    mkdir -p "$GWS_MEMORY_DIR/actions"
    echo "$entry" >> "$GWS_MEMORY_DIR/actions/${action}.jsonl"

    # Auto-update contact node if it exists
    if get_contact_file "$contact" &>/dev/null; then
        update_contact "$contact" "last_contact" "$(date +%Y-%m-%d)"
        update_contact "$contact" "observations" "+1"

        # Add account to accounts_seen if not present
        local contact_file
        contact_file=$(get_contact_file "$contact")
        if ! grep -q "$account" "$contact_file" 2>/dev/null; then
            # Simple approach: Claude will manage the array properly during skill execution
            :
        fi
    fi

    echo "Logged: $action for $contact on $account"
}

# --- Preamble Helpers ---

# Print loaded memory context summary (for preamble output)
print_memory_summary() {
    local contact_count=0 topic_count=0 action_count=0

    # Count contacts
    for f in "$GWS_MEMORY_DIR"/contacts/*.md; do
        [[ -f "$f" && "$(basename "$f")" != ".gitkeep" ]] && ((contact_count++)) || true
    done

    # Count topics
    for f in "$GWS_MEMORY_DIR"/topics/*.md; do
        [[ -f "$f" && "$(basename "$f")" != ".gitkeep" && "$(basename "$f")" != "scheduling-preferences.md" ]] && ((topic_count++)) || true
    done

    # Count action entries
    for f in "$GWS_MEMORY_DIR"/actions/*.jsonl; do
        [[ -f "$f" ]] && action_count=$((action_count + $(wc -l < "$f"))) || true
    done

    echo "Memory: $contact_count contacts, $topic_count topics, $action_count actions logged"
}

# Load and print all personas (excluding example.md)
print_personas() {
    for persona_file in "$GWS_OS_DIR"/accounts/personas/*.md; do
        [[ -f "$persona_file" && "$(basename "$persona_file")" != "example.md" ]] || continue
        echo "--- $(basename "$persona_file") ---"
        cat "$persona_file"
        echo ""
    done
}

# Load and print all contact nodes (first 20 lines each)
print_contacts() {
    local found=false
    for contact_file in "$GWS_MEMORY_DIR"/contacts/*.md; do
        [[ -f "$contact_file" && "$(basename "$contact_file")" != ".gitkeep" ]] || continue
        found=true
        echo "--- $(basename "$contact_file") ---"
        head -20 "$contact_file"
        echo ""
    done
    $found || echo "  No contacts in memory yet."
}

# Load and print all topic nodes
print_topics() {
    local found=false
    for topic_file in "$GWS_MEMORY_DIR"/topics/*.md; do
        [[ -f "$topic_file" && "$(basename "$topic_file")" != ".gitkeep" && "$(basename "$topic_file")" != "scheduling-preferences.md" ]] || continue
        found=true
        echo "--- $(basename "$topic_file") ---"
        cat "$topic_file"
        echo ""
    done
    $found || echo "  No topics in memory yet."
}
