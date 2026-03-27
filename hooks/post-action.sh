#!/usr/bin/env bash
set -euo pipefail

# post-action.sh — Called after any gws action to log to memory nodes
# Usage: bash post-action.sh <action> <account_id> <contact_email> [topic] [extra_json]
#
# Phase 1-2: Appends to memory/actions/{action}.jsonl
# Phase 3-4: Also writes graph edges via gws-graph-write.py

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

echo "Logged: $ACTION by $CONTACT on $ACCOUNT"
