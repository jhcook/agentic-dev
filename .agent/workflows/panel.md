---
description: Convene the AI Governance Panel for expert consultation.
---

# Panel Consultation

## PURPOSE

This is a **Consultative** session — unlike `preflight`, the panel is NOT a gatekeeper. It acts as a board of experts providing advice, warnings, and recommendations. No BLOCK/PASS verdicts — only advisory framing.

## PROCESS

1. **Run** `agent panel <STORY-ID>` for consultative governance review.
2. **Compare branches** with `agent panel <STORY-ID> --base main`.
3. **Auto-apply** with `agent panel <STORY-ID> --apply` to inject advice into story/runbook.
4. **Ask questions** with `agent panel "How should we approach X for INFRA-069?"`.
5. **Override engine** with `agent panel <STORY-ID> --panel-engine adk|native`.

## FLAGS

| Flag | Description |
|------|-------------|
| `--base <branch>` | Compare against a specific branch (default: staged changes) |
| `--provider <name>` | Force AI provider (gh, gemini, vertex, openai, anthropic) |
| `--apply` | Auto-apply panel advice to story/runbook file |
| `--panel-engine <engine>` | Override panel engine: `adk` or `native` |

## OUTPUT

The command produces a **Governance Panel Consultation** report with:

- Per-role expert commentary (@Architect, @Security, @QA, @Compliance, @Product, etc.)
- Sentiment indicators (Positive / Neutral / Negative)
- Actionable recommendations per role
- Consensus summary

## NOTES

- Use **Advice** and **Recommendations** framing, not BLOCK/PASS
- Panel reads story/runbook context automatically
- If no changes are staged, the panel operates in **Design Review mode** (document context only)
- See `agent panel --help` for all options
