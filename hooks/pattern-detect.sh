#!/usr/bin/env bash
set -euo pipefail

# pattern-detect.sh — Triggered when a contact/topic node reaches 5+ observations
# Reads action logs for a contact, identifies recurring (action, topic) sequences,
# and writes pattern fields to topic nodes.
#
# Phase 1-2: Basic frequency counting from JSONL action logs
# Phase 3-4: Uses graph edges for richer pattern detection
#
# Usage: bash pattern-detect.sh <contact_email>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTIONS_DIR="$SCRIPT_DIR/memory/actions"
CONTACTS_DIR="$SCRIPT_DIR/memory/contacts"
TOPICS_DIR="$SCRIPT_DIR/memory/topics"

CONTACT="${1:?Usage: pattern-detect.sh <contact_email>}"

echo "Checking patterns for: $CONTACT"

# Count total observations across all action types
TOTAL=0
for ACTION_FILE in "$ACTIONS_DIR"/*.jsonl; do
    [[ -f "$ACTION_FILE" ]] || continue
    COUNT=$(grep -c "\"contact\":\"$CONTACT\"" "$ACTION_FILE" 2>/dev/null || echo 0)
    TOTAL=$((TOTAL + COUNT))
done

echo "Total observations for $CONTACT: $TOTAL"

if [[ $TOTAL -lt 5 ]]; then
    echo "Below threshold (5). No pattern detection yet."
    exit 0
fi

echo "Threshold reached. Pattern detection will be handled by Claude during skill execution."
echo "Claude reads action logs and contact nodes directly in Phase 1-2."
