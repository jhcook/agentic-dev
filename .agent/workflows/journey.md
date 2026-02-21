---
description: Create a new user journey from conversation context.
---

# Workflow: Create User Journey

A journey defines **what the system does from a user's perspective** — it is a behavioral contract that the agent codes against and protects during future implementations.

**Journeys come BEFORE stories.** See `.agent/docs/user_journeys.md` for the full lifecycle.

## Steps

1. **Scaffold**: Run `agent new-journey <JRN-ID>` (or omit the ID for auto-generation).
   - By default, the AI generates a fully populated journey from a brief description.
   - Add `--offline` to disable the AI and use manual input.
   - Add `--provider <provider>` to force a specific AI provider (gh, gemini, vertex, openai, anthropic).

2. **Review and Refine the Journey YAML**:
   - **AI-generated**: Review and refine the output — pay particular attention to assertions (are they specific and verifiable?) and error paths (are the obvious failure modes covered?).
   - **Manual (`--offline`)**: Read `.agent/docs/journey_yaml_spec.md` — this is the canonical field reference.
     - Fill in the **required fields** from the current conversation context:
       - `id`, `title`, `actor`, `description`, `steps`
     - For each step, write a concrete `action`, `system_response`, and at least one `assertion`.
     - Add optional fields only when they add value:
       - `error_paths` — when the happy path has known failure modes
       - `edge_cases` — for race conditions, idempotency, or security boundaries
       - `preconditions` — when external state must exist
       - `auth_context` — when permissions are required
       - `data_state` — when you need to track data mutations
       - `branches` — when conditional flows exist (A/B, feature flags, SSO vs password)
     - Leave `implementation` blocks empty — the agent populates these during `/implement`.

3. **Panel Consultation** (Advisory):
   - Run `agent panel <JRN-ID>` to invoke the AI Governance Panel for a consultative review of the journey.
   - The panel (@Product, @Architect, @Security, @QA, @Compliance) will analyze the journey steps, assertions, and edge cases.
   - This is **consultative** — the panel provides advice, not blocking verdicts.
   - Review the panel's feedback and adjust the journey file accordingly.

4. **Finalize**:
   - Set `state: COMMITTED` once you are satisfied the journey is complete.
   - Confirm the journey file is saved in `.agent/cache/journeys/`.

## Output

The populated YAML file at `.agent/cache/journeys/<JRN-ID>-<safe-title>.yaml`.

## Rules

- Use `yaml.safe_load()` patterns — never `yaml.load()`.
- Assertions must be **verifiable** — avoid vague statements like "works correctly".
- Every step must have at least one assertion.
- Do NOT pre-populate `implementation` blocks — those are filled during implementation.
- Keep journeys focused. One journey = one complete user goal. If it branches into a fundamentally different goal, create a separate journey and use `depends_on`.
