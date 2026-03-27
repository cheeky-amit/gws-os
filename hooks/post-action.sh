#!/usr/bin/env bash
set -euo pipefail

# post-action.sh — Called after any gws action to log to memory nodes
# Usage: bash post-action.sh <action> <account_id> <contact_email> [topic] [extra_json]
#
# Tier 1 storage (CAR Protocol): raw action events in JSONL.
# When a contact crosses the consolidation threshold (5 observations),
# triggers pattern-detect.sh for Tier 2/3 promotion.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTIONS_DIR="$SCRIPT_DIR/memory/actions"

ACTION="${1:?Usage: post-action.sh <action> <account_id> <contact_email> [topic]}"
ACCOUNT="${2:?}"
CONTACT="${3:?}"
TOPIC="${4:-}"
EXTRA="${5:-}"

mkdir -p "$ACTIONS_DIR"

# Build action log entry
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
ENTRY=$(jq -n \
    --arg ts "$TS" \
    --arg action "$ACTION" \
    --arg account "$ACCOUNT" \
    --arg contact "$CONTACT" \
    --arg topic "$TOPIC" \
    '{ts: $ts, action: $action, account: $account, contact: $contact, topic: $topic}')

# Append to action-type JSONL file
echo "$ENTRY" >> "$ACTIONS_DIR/${ACTION}.jsonl"

# Also log to daily automate log if this was an automated action
if [[ "${GWS_TRUST_LEVEL:-}" == "automate" ]]; then
    DATE=$(date +"%Y-%m-%d")
    echo "$ENTRY" >> "$ACTIONS_DIR/automate-log-${DATE}.jsonl"
fi

# Check if contact crossed the consolidation threshold (5 observations)
# If so, trigger pattern detection for Tier 2/3 promotion (CAR Protocol)
OBS_COUNT=0
for AF in "$ACTIONS_DIR"/*.jsonl; do
    [[ -f "$AF" ]] || continue
    C=$(grep -c "\"contact\":\"$CONTACT\"" "$AF" 2>/dev/null || echo 0)
    OBS_COUNT=$((OBS_COUNT + C))
done

if [[ $OBS_COUNT -ge 5 ]]; then
    echo "Consolidation threshold reached ($OBS_COUNT observations). Triggering pattern detection."
    bash "$SCRIPT_DIR/hooks/pattern-detect.sh" "$CONTACT"
fi

echo "Logged: $ACTION by $CONTACT on $ACCOUNT"
