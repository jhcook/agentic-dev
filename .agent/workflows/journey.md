---
description: Create a new user journey from conversation context.
---

# Workflow: Create User Journey

A journey defines **what the system does from a user's perspective** — it is a behavioral contract that the agent codes against and protects during future implementations.

**Journeys come BEFORE stories.** See `.agent/docs/user_journeys.md` for the full lifecycle.

## Steps

1. **Scaffold**: Run `agent new-journey <JRN-ID>` (or omit the ID for auto-generation).
   - Add `--ai` to have the AI generate a populated journey from a brief description.
   - Add `--provider <provider>` to force a specific AI provider (gh, gemini, openai).

2. **Populate the Journey YAML**:
   - **With `--ai`**: The AI generates a fully populated YAML journey. Review and refine the output — pay particular attention to assertions (are they specific and verifiable?) and error paths (are the obvious failure modes covered?).
   - **Without `--ai`** (manual): Read `.agent/docs/journey_yaml_spec.md` — this is the canonical field reference.
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

3. **Panel Consultation** (Optional):
   - Use the `--panel` flag to run an automated consultative panel review:

     ```bash
     agent new-journey <JRN-ID> --ai --panel
     ```

   - All roles from `.agent/etc/agents.yaml` will review the journey and append feedback as comments in the YAML file.

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
