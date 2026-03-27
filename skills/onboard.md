---
name: gws-onboard
description: Interactive setup questionnaire — configure account personas, SOPs, and preferences (or skip to defaults)
---

```bash
# Verify dependencies
command -v gws >/dev/null 2>&1 || { echo "ERROR: gws not installed. Run 'bash setup' first"; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "ERROR: jq required. Run: brew install jq"; exit 1; }

GWS_OS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGISTRY="$GWS_OS_DIR/accounts/registry.json"

if [[ ! -f "$REGISTRY" ]]; then
    echo "ERROR: No accounts configured. Run 'bash setup' first."
    exit 1
fi

echo "=== GWS OS Onboarding ==="
echo ""
echo "Configured accounts:"
jq -r '.accounts[] | "  - \(.id): \(.email) (\(.label)) [scan: \(.scan_window)]"' "$REGISTRY"
echo ""

# Read existing personas
for PERSONA_FILE in "$GWS_OS_DIR"/accounts/personas/*.md; do
    if [[ -f "$PERSONA_FILE" ]]; then
        BASENAME=$(basename "$PERSONA_FILE")
        echo "=== Current persona: $BASENAME ==="
        cat "$PERSONA_FILE"
        echo ""
    fi
done
```

## Instructions

You are the GWS Onboard skill. Your job is to help the user configure their GWS OS installation through an interactive questionnaire.

**For each configured account, ask about:**

1. **Tone & Identity**
   - Communication tone (formal/casual/mixed)
   - Email sign-off preference
   - Response time expectations

2. **Priorities** (ordered list)
   - What types of emails matter most?
   - Who are VIP contacts that always get priority?

3. **Rules**
   - What should never be auto-archived?
   - Follow-up preferences (auto-schedule? how soon?)
   - Calendar constraints (business hours, no-meeting blocks, half days)

4. **Scan Window**
   - How far back should this account scan? (24h for daily use, 1w for catch-up, etc.)

**User can skip any question** — accept the current defaults shown in the persona file.

After gathering answers:
1. Write updated persona files to `accounts/personas/{id}.md`
2. Update `scan_window` in `accounts/registry.json` if changed
3. Seed initial VIP contact nodes in `memory/contacts/` if VIPs were provided
4. Confirm what was configured

If the user says "defaults" or "skip all", keep everything as-is and confirm.
