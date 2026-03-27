#!/usr/bin/env bash
set -euo pipefail

# pattern-detect.sh — CAR Protocol Tier 2 → Tier 3 promotion
# Triggered when a contact crosses 5+ observations (consolidation threshold).
# Scans action logs for recurring (action, topic) pairs per contact.
# Recurring pairs (>= 3 occurrences) are promoted to graph edges and
# topic nodes get their pattern field updated.
#
# Usage: bash pattern-detect.sh <contact_email>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTIONS_DIR="$SCRIPT_DIR/memory/actions"
TOPICS_DIR="$SCRIPT_DIR/memory/topics"
GRAPH_TOOL="$SCRIPT_DIR/bin/gws-graph.py"

CONTACT="${1:?Usage: pattern-detect.sh <contact_email>}"

echo "=== CAR Pattern Detection for: $CONTACT ==="

# --- Step 1: Count total observations across all action JSONL files ---
TOTAL=0
for ACTION_FILE in "$ACTIONS_DIR"/*.jsonl; do
    [[ -f "$ACTION_FILE" ]] || continue
    COUNT=$(grep -c "\"contact\":\"$CONTACT\"" "$ACTION_FILE" 2>/dev/null || echo 0)
    TOTAL=$((TOTAL + COUNT))
done

echo "Total observations: $TOTAL"

if [[ $TOTAL -lt 5 ]]; then
    echo "Below consolidation threshold (5). Skipping."
    exit 0
fi

# --- Step 2: Extract all (action, topic) pairs for this contact ---
# Collect matching lines from all JSONL files into a temp file
TMPFILE=$(mktemp)
trap 'rm -f "$TMPFILE"' EXIT

for ACTION_FILE in "$ACTIONS_DIR"/*.jsonl; do
    [[ -f "$ACTION_FILE" ]] || continue
    grep "\"contact\":\"$CONTACT\"" "$ACTION_FILE" 2>/dev/null >> "$TMPFILE" || true
done

# --- Step 3: Find recurring (action, topic) pairs (>= 3 occurrences) ---
# Extract action+topic pairs using jq, count occurrences, filter >= 3
if ! command -v jq &>/dev/null; then
    echo "Warning: jq not found. Cannot analyze patterns."
    exit 0
fi

PAIRS=$(jq -r 'select(.topic != "") | "\(.action)\t\(.topic)"' "$TMPFILE" 2>/dev/null \
    | sort | uniq -c | sort -rn \
    | awk '$1 >= 3 { print $1 "\t" $2 "\t" $3 }')

if [[ -z "$PAIRS" ]]; then
    echo "No recurring (action, topic) pairs found (need >= 3 occurrences)."
    exit 0
fi

echo "Recurring patterns detected:"
echo "$PAIRS" | while IFS=$'\t' read -r FREQ ACTION TOPIC; do
    echo "  $ACTION + $TOPIC  ($FREQ times)"
done

# --- Step 4: Write graph edges for recurring pairs (Tier 3 promotion) ---
echo "$PAIRS" | while IFS=$'\t' read -r FREQ ACTION TOPIC; do
    # Write graph edge if gws-graph.py exists
    if [[ -x "$GRAPH_TOOL" ]]; then
        echo "Writing graph edge: $CONTACT --[$ACTION]--> $TOPIC (weight: $FREQ)"
        python3 "$GRAPH_TOOL" write \
            --from "$CONTACT" \
            --to "$TOPIC" \
            --relation "$ACTION" \
            --weight "$FREQ" 2>/dev/null || echo "  Warning: graph write failed for $ACTION->$TOPIC"
    else
        echo "Note: bin/gws-graph.py not found yet. Skipping graph write for $ACTION->$TOPIC"
    fi

    # Update topic node's pattern field if the topic file exists
    TOPIC_SLUG=$(echo "$TOPIC" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | sed 's/[^a-z0-9-]//g')
    TOPIC_FILE="$TOPICS_DIR/${TOPIC_SLUG}.md"
    if [[ -f "$TOPIC_FILE" ]]; then
        CURRENT_PATTERN=$(grep '^pattern:' "$TOPIC_FILE" | head -1 | sed 's/^pattern: *//' | tr -d '"')
        NEW_PATTERN="$CONTACT:$ACTION(x$FREQ)"
        if [[ -z "$CURRENT_PATTERN" ]]; then
            sed -i '' "s/^pattern: .*/pattern: \"$NEW_PATTERN\"/" "$TOPIC_FILE"
            echo "  Updated topic node pattern: $NEW_PATTERN"
        elif [[ "$CURRENT_PATTERN" != *"$CONTACT:$ACTION"* ]]; then
            COMBINED="$CURRENT_PATTERN; $NEW_PATTERN"
            sed -i '' "s/^pattern: .*/pattern: \"$COMBINED\"/" "$TOPIC_FILE"
            echo "  Appended to topic node pattern: $NEW_PATTERN"
        else
            echo "  Topic node already contains this pattern."
        fi
    fi
done

echo "=== Pattern detection complete ==="
