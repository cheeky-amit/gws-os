---
name: gws-onboard
description: Interactive setup questionnaire — configure account personas, SOPs, and preferences (or skip to defaults)
---

```bash
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/gws-common.sh"
gws_init

echo "=== GWS OS Onboarding ==="
echo ""
echo "Configured accounts:"
print_accounts
echo ""

# Read existing personas
echo "=== Current Personas ==="
print_personas
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
