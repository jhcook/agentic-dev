# Manual Implementation Guide & Best Practices

This document preserves the comprehensive, gate-driven implementation workflow
as a set of best practices. While the `agent implement` CLI command now
automates the majority of this process (including journey checks, incremental
loops, and governance gates), this guide serves as the definitive reference for
how the agent should reason about implementation when operating manually or when
the CLI cannot be used.

## PURPOSE

Implement a feature, fix, or enhancement following strict quality gates:

1. Design review by @Architect
1. Security scan by @Security
1. Quality assurance by @QA
1. Documentation by @Docs
1. Compliance by @Compliance
1. Observability by @Observability

______________________________________________________________________

## WORKFLOW

### PHASE 0: PRE-VALIDATION

1. **Update Story State**
   - Locate the Story file related to this Runbook.
   - Change the `## State` status to `IN_PROGRESS`.
   - Run `agent sync` to propagate this change to Notion.

### PHASE 0.5: JOURNEY GATE

> [!IMPORTANT] User journeys are a **prerequisite for implementation**
> (ADR-024). This gate prevents implementing stories that have no defined
> behavioral contract.

1. **Check Linked Journeys**

   - Read the story's `## Linked Journeys` section.
   - Extract the journey IDs (e.g., `JRN-001`, `JRN-005`).

1. **Validate Journey Files Exist**

   - For each linked journey ID, check that a matching YAML file exists in
     `.agent/cache/journeys/`.
   - If a journey file is **missing**:
     `❌ Journey JRN-XXX not found. Run 'agent new-journey JRN-XXX' first.` →
     **BLOCK**
   - If `## Linked Journeys` is **empty or only contains the placeholder**
     (`JRN-XXX`):
     - `⚠️ No journeys linked to this story. Use --skip-journey-check to
       proceed without journeys.`
     - → **BLOCK** (unless `--skip-journey-check` is set)

1. **Load Journey Context**

   - If journeys exist, load their YAML content for use in subsequent phases.
   - Pass journey assertions to @QA in Phase 4 for test coverage validation.
   - Pass journey implementation mappings to Phase 2 for file overlap detection.

______________________________________________________________________

### PHASE 1: REQUIREMENTS & DESIGN

**@Architect** leads this phase:

1. **Clarify Requirements**

   - If the requirement is ambiguous, ask clarifying questions
   - Identify affected components, trust boundaries, data flows
   - Assess impact: Is this a new feature, bug fix, refactor, or enhancement?

1. **Design Review**

   - Check for architectural impacts:
     - New API endpoints or data flows?
     - Changes to security boundaries?
     - New dependencies or external integrations?
     - Data retention or deletion implications? (GDPR)
   - **API Contract Review (MANDATORY for API changes)**:
     - If changes affect `src/servers/rest_server.py` or `src/core/models.py`:
       - Load current OpenAPI spec from `docs/openapi.yaml`
       - Identify all affected endpoints and models
       - Determine if changes are BREAKING or NON-BREAKING
       - BREAKING changes require:
         - Explicit justification
         - Migration plan for existing clients
         - Versioning strategy (if applicable)
         - Documentation of deprecation timeline
       - NON-BREAKING changes require:
         - Confirmation that OpenAPI spec will be updated
         - Verification of backward compatibility
   - Identify affected files/modules
   - Design approach following existing patterns

1. **SOC 2 + GDPR Impact Assessment**

   - Does this handle personal data? → Document lawful basis, retention,
     deletion
   - Does this create new logs? → Ensure no PII in logs
   - Does this expose new endpoints? → Authentication required?
   - Does this store secrets? → Use environment variables, never commit

______________________________________________________________________

### PHASE 2: IMPLEMENTATION

**@BackendEngineer** (Python) or **@FrontendDev** (React/TypeScript) leads:

#### Backend Code

Focus:

- Logic conversion.

Rule:

- Functional equivalence, NOT line-by-line translation.
- Use Pythonic idioms (list comprehensions, context managers).

Compliance:

- Must follow global compliance requirements.
- Must not introduce code that @Security (security/SOC 2) or @QA (lint/tests)
  would BLOCK.
- Before finalizing output, do a brief self-check:
  - Are there any secrets, tokens, or PII in code or logs?
  - Would this pass the project’s linting and type checks?
  - Have I added or updated tests where behavior changed?

GDPR Self-Check:

- No personal data is written to logs.
- No personal data is persisted client-side without justification.
- New forms or inputs collecting personal data have clear purpose and secure
  transmission.
- No analytics or telemetry includes raw personal data.

#### Frontend Code

Focus:

- UX-first implementation.
- Build screens, flows, and state management in React Native (and related
  frontend stack) that match the described behavior.

Compliance:

- Must follow global compliance requirements.
- Must not introduce code that @Security (security/SOC 2) or @QA (lint/tests)
  would BLOCK.

Rule:

- Functional equivalence, not pixel-perfect cloning.
- Use idiomatic React (hooks, components, context), platform conventions
  (navigation, gestures), and handle loading/error/empty states.
- When APIs, storage, or auth are involved, wire them up using best-practice
  patterns for the given stack.

**Error Handling (MANDATORY for ALL API calls)**: Every UI operation that calls
an API or performs async work MUST:

- Catch errors and display them to the user (never silently swallow).
- Show specific, actionable error messages.
- Use appropriate UI patterns (Toast, Modal, Inline).
- Always log errors to console for debugging.

GDPR Self-Check:

- Error messages do not expose other users' personal data.

#### Execution Rules

1. **Code Changes**

   - Follow patterns from existing codebase.
   - Minimal surgical changes (no refactoring unless necessary).
   - Type hints for Python, proper TypeScript types.
   - Docstrings for public APIs.

1. **Incremental Verification (MANDATORY)**

   > [!CAUTION] After EVERY file modification, run `make test`. Do NOT batch
   > multiple file changes before testing.

   ```bash
   make test
   ```

   **If tests fail:**

   - Attempt to fix the regression immediately (max 2 attempts).
   - If still failing after 2 attempts: rollback the last change and report what
     went wrong.
   - Do NOT proceed to the next file until tests pass.

______________________________________________________________________

### PHASE 3: SECURITY REVIEW

**@Security** leads this phase:

1. **Security Scan**

   - [ ] No secrets in code (API keys, passwords, tokens)
   - [ ] Input validation on all user inputs
   - [ ] SQL injection prevention (parameterized queries)
   - [ ] No eval() or exec() on user input
   - [ ] File uploads validated (type, size, content)
   - [ ] Authentication/authorization enforced
   - [ ] HTTPS/TLS for external calls
   - [ ] Secrets redacted in logs and errors

1. **Privacy Review (GDPR)**

   - [ ] No PII in logs
   - [ ] Personal data has clear purpose
   - [ ] Retention/deletion policy documented
   - [ ] Third-party data transfers documented

1. **SOC 2 Technical Controls**

   - [ ] Logging for audit trail
   - [ ] Error handling doesn't leak internals
   - [ ] Timeouts on external API calls
   - [ ] Rate limiting where appropriate

______________________________________________________________________

### PHASE 4: QUALITY ASSURANCE

**@QA** leads this phase:

1. **Python Code Validation** (if Python changes)

   ```bash
   # Syntax check
   python -m py_compile <files>

   # Code quality
   uv run pyflakes <files>

   # Run related tests
   pytest tests/test_<relevant>.py -v
   ```

1. **TypeScript Validation** (if UI changes)

   ```bash
   # Type check
   cd ui && npx tsc --noEmit

   # Lint check
   cd ui && npx eslint src/**/*.{ts,tsx}

   # Build check
   cd ui && npm run build
   ```

1. **OpenAPI Spec Validation** (if API changes)

   ```bash
   # Regenerate OpenAPI spec
   python scripts/generate_openapi.py

   # Compare with committed version
   git diff docs/openapi.yaml

   # Verify changes are intentional and documented
   # BLOCK if unexpected changes or spec not updated
   ```

1. **Functional Testing**

   - [ ] Code compiles/builds without errors
   - [ ] Existing tests still pass
   - [ ] New functionality works as expected
   - [ ] Edge cases handled
   - [ ] Error paths tested

1. **Test Coverage**

   - New API endpoints → Integration test required
   - Core logic changes → Unit tests required
   - Critical flows → Must pass existing tests

______________________________________________________________________

### PHASE 5: DOCUMENTATION

**@Scribe** leads this phase:

1. **Code Documentation**

   - [ ] Docstrings present and accurate
   - [ ] Complex logic has inline comments
   - [ ] Type hints/annotations complete
   - [ ] API changes documented

1. **API Documentation** (if API changes)

   - [ ] OpenAPI spec updated (`docs/openapi.yaml`)
   - [ ] Breaking changes documented in CHANGELOG
   - [ ] Migration guide created (if breaking changes)
   - [ ] Deprecation notices added to affected endpoints
   - [ ] API usage examples updated

1. **User Documentation** (if user-facing)

   - [ ] README updated (if new feature)
   - [ ] Configuration changes documented
   - [ ] Breaking changes noted

1. **Compliance Documentation** (if required)

   - [ ] Data handling documented
   - [ ] Security controls documented
   - [ ] Privacy impact documented

______________________________________________________________________

### PHASE 6: COMPLETION SYNC

1. **Auto-Stage**

   - When all governance gates pass, stage:
     - All modified implementation files
     - The story file (state updated to IN_PROGRESS)
     - The runbook file
   - Output: `📦 Staged N file(s) for commit.`

1. **Preflight**

   - Run `agent preflight --ai --story <STORY-ID>` to validate staged changes
     against the Governance Council, then commit.

## RULES

1. **No shortcuts** - All phases must complete
1. **Surgical changes only** - Minimal edits to achieve goal
1. **Security first** - @Security veto power
1. **Quality gate** - @QA validates all code changes
1. **Documentation** - @Scribe ensures auditability
1. **Fail fast** - Stop at first BLOCK, report clearly
