---
name: gws
description: Learning-first Google Workspace CLI — multi-account email, calendar, drive orchestration with memory and trust progression
---

# GWS OS

A learning-first Google Workspace orchestration system for Claude Code.

## Available Commands

| Command | Description | Phase |
|---------|-------------|-------|
| `/gws onboard` | Interactive setup — configure personas, SOPs, or use defaults | 1 |
| `/gws triage` | Email triage across accounts with categorization | 1 |
| `/gws morning` | Full morning triage with priority ranking | 2 |
| `/gws reply` | Context-aware reply from the right account | 2 |
| `/gws plan` | Schedule intelligence — flags conflicts, learns your preferences | 3 |
| `/gws schedule` | Cross-calendar scheduling | 3 |
| `/gws brief` | Pre-meeting intelligence brief | 3 |
| `/gws followup` | Track and remind follow-ups | 3 |
| `/gws search` | Cross-account, cross-service search | 3 |
| `/gws weekly` | Weekly review and learning report | 4 |
| `/gws learn` | Show learned patterns, trust levels, undo actions | 4 |

## Setup

Run `/gws onboard` or the `setup` script to configure accounts and personas.

## How It Works

1. **Preamble** fetches lightweight context (headers, account registry, memory nodes)
2. **Claude** analyzes, categorizes, and proposes actions
3. **User confirms** all send/reply/schedule actions (mandatory gate)
4. **Memory** updates — contact and topic nodes grow with each interaction
5. **Trust** progresses per action+contact: observe → suggest → assist → automate
