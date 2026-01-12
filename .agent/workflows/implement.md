# implement

You are an implementation agent for this repository following .agent/rules/ governance.

## PURPOSE

Implement a feature, fix, or enhancement following strict quality gates:
1. Design review by @Architect
2. Security scan by @Security
3. Quality assurance by @QA
4. Documentation by @Docs
5. Compliance by @Compliance
6. Observability by @Observability

## SYNTAX

```bash
agent implement <RUNBOOK-ID>
```

## SCOPE

User provides a requirement. You must:
- Understand the requirement fully
- Design the implementation
- Execute the implementation
- Validate compliance
- Document the changes

## WORKFLOW

### PHASE 1: REQUIREMENTS & DESIGN

**@Architect** leads this phase:

1. **Clarify Requirements**
   - If the requirement is ambiguous, ask clarifying questions
   - Identify affected components, trust boundaries, data flows
   - Assess impact: Is this a new feature, bug fix, refactor, or enhancement?

2. **Design Review**
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

3. **SOC 2 + GDPR Impact Assessment**
   - Does this handle personal data? → Document lawful basis, retention, deletion
   - Does this create new logs? → Ensure no PII in logs
   - Does this expose new endpoints? → Authentication required?
   - Does this store secrets? → Use environment variables, never commit

**VERDICT: PROCEED | CLARIFY | BLOCK**
- PROCEED: Design is sound, move to implementation
- CLARIFY: Need more information from user
- BLOCK: Architectural concern prevents implementation

---

### PHASE 2: IMPLEMENTATION

**@BackendEngineer** (Python) or **@FrontendDev** (React/TypeScript) leads:

### Backend Code:
   Focus: 
   - Logic conversion.

   Rule: 
   - Functional equivalence, NOT line-by-line translation. 
   - Use Pythonic idioms (list comprehensions, context managers).
   
   Compliance:
   - Must follow **Global Compliance Requirements**.
   - Must not introduce code that @Security (security/SOC 2) or @QA (lint/tests) would BLOCK.
   - Before finalizing output, do a brief self-check:
      - Are there any secrets, tokens, or PII in code or logs?
      - Would this pass the project’s linting and type checks?
      - Have I added or updated tests where behavior changed?
   
   GDPR Self-Check:
   Before final output, verify:
   - No personal data is written to logs.
   - No personal data is persisted client-side without justification.
   - New forms or inputs collecting personal data have:
      - Clear purpose.
      - Secure transmission.
   - No analytics or telemetry includes raw personal data.

   Output: 
   - Working Python code.

### Frontend Code:
   Focus: 
   - UX-first implementation. 
   - Build screens, flows, and state management in React Native (and related frontend stack) that match the described behavior.
   
   Compliance:
   - Must follow **Global Compliance Requirements**.
   - Must not introduce code that @Security (security/SOC 2) or @QA (lint/tests) would BLOCK.
   - Before finalizing output, do a brief self-check:
      - Are there any secrets, tokens, or PII in code or logs?
      - Would this pass the project’s linting and type checks?
      - Have I added or updated tests where behavior changed?

   Rule: 
   - Functional equivalence, not pixel-perfect cloning. 
   - Use idiomatic React (hooks, components, context), platform conventions (navigation, gestures), and handle loading/error/empty states. 
   - When APIs, storage, or auth are involved, wire them up using best-practice patterns for the given stack (React Native, web React, or shared TypeScript utilities).

   **Error Handling (MANDATORY for ALL API calls)**:
   Every UI operation that calls an API or performs async work MUST:
   - Catch errors and display them to the user (never silently swallow)
   - Show specific, actionable error messages:
      - What failed: operation + filename/identifier
      - Why it failed: actual error message from backend
      - What to do: "contact support", "try again", "check settings"
   - Use appropriate UI patterns:
      - Toast notifications for transient errors (10s duration)
      - Modal dialogs for blocking errors requiring acknowledgment
      - Inline error text for form validation
   - Always log errors to console for debugging
   - For critical failures: provide "Copy Error Details" functionality
   - Show summaries for multiple failures: first 3 + "...and N more"
   
   Examples of UNACCEPTABLE error handling:
   - `catch (err) { skipped += 1 }` ❌ Silent failure
   - `toast.error("Failed")` ❌ No context about what/why
   - `console.error(err); return;` ❌ User sees nothing
   
   Examples of REQUIRED error handling:
   - `toast.error(\`Upload failed: \${file.name}\n\${err.message}\n\nContact support.\`, {duration: 10000})`
   - Collect errors array, show first 3 with "...and N more" summary
   - Provide copy-to-clipboard for full error details

   GDPR Self-Check:
   Before final output, verify:
   - No personal data is written to logs.
   - No personal data is persisted client-side without justification.
   - New forms or inputs collecting personal data have:
      - Clear purpose.
      - Secure transmission.
   - No analytics or telemetry includes raw personal data.
   - Error messages do not expose other users' personal data.
   
   Output: 
   - Working React/React Native code (TS/JS + JSX/TSX) with any necessary styles, helper functions, and minimal glue code (navigation wiring, API calls, etc.) so it can be dropped into the existing app.

1. **Code Changes**
   - Follow patterns from existing codebase
   - Minimal surgical changes (no refactoring unless necessary)
   - Type hints for Python, proper TypeScript types
   - Docstrings for public APIs
   - Follow .agent/rules/lean-code.mdc conventions

2. **Implementation Checklist**
   - [ ] Code follows existing patterns
   - [ ] Type annotations present
   - [ ] Docstrings for new functions/classes
   - [ ] Error handling in place
   - [ ] No hardcoded secrets
   - [ ] Logging doesn't leak PII
   - [ ] Input validation for user-facing code

3. **File Changes**
   - Use `view`, `edit`, `create` tools
   - Make minimal, targeted changes
   - Preserve existing functionality

**VERDICT: IMPLEMENTED | BLOCKED**
- IMPLEMENTED: Code changes complete
- BLOCKED: Technical issue prevents implementation

---

### PHASE 3: SECURITY REVIEW

**@Sentinel** leads this phase:

1. **Security Scan**
   - [ ] No secrets in code (API keys, passwords, tokens)
   - [ ] Input validation on all user inputs
   - [ ] SQL injection prevention (parameterized queries)
   - [ ] No eval() or exec() on user input
   - [ ] File uploads validated (type, size, content)
   - [ ] Authentication/authorization enforced
   - [ ] HTTPS/TLS for external calls
   - [ ] Secrets redacted in logs and errors

2. **Privacy Review (GDPR)**
   - [ ] No PII in logs
   - [ ] Personal data has clear purpose
   - [ ] Retention/deletion policy documented
   - [ ] Third-party data transfers documented

3. **SOC 2 Technical Controls**
   - [ ] Logging for audit trail
   - [ ] Error handling doesn't leak internals
   - [ ] Timeouts on external API calls
   - [ ] Rate limiting where appropriate

**VERDICT: APPROVE | BLOCK**
- APPROVE: No security issues
- BLOCK: Security issue requires fix

---

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

2. **TypeScript Validation** (if UI changes)
   ```bash
   # Type check
   cd ui && npx tsc --noEmit
   
   # Lint check
   cd ui && npx eslint src/**/*.{ts,tsx}
   
   # Build check
   cd ui && npm run build
   ```

3. **OpenAPI Spec Validation** (if API changes)
   ```bash
   # Regenerate OpenAPI spec
   python scripts/generate_openapi.py
   
   # Compare with committed version
   git diff docs/openapi.yaml
   
   # Verify changes are intentional and documented
   # BLOCK if unexpected changes or spec not updated
   ```

4. **Functional Testing**
   - [ ] Code compiles/builds without errors
   - [ ] Existing tests still pass
   - [ ] New functionality works as expected
   - [ ] Edge cases handled
   - [ ] Error paths tested

5. **Test Coverage**
   - New API endpoints → Integration test required
   - Core logic changes → Unit tests required
   - Critical flows → Must pass existing tests

**VERDICT: APPROVE | BLOCK**
- APPROVE: All checks pass
- BLOCK: Quality issue requires fix

---

### PHASE 5: DOCUMENTATION

**@Scribe** leads this phase:

1. **Code Documentation**
   - [ ] Docstrings present and accurate
   - [ ] Complex logic has inline comments
   - [ ] Type hints/annotations complete
   - [ ] API changes documented

2. **API Documentation** (if API changes)
   - [ ] OpenAPI spec updated (`docs/openapi.yaml`)
   - [ ] Breaking changes documented in CHANGELOG
   - [ ] Migration guide created (if breaking changes)
   - [ ] Deprecation notices added to affected endpoints
   - [ ] API usage examples updated

3. **User Documentation** (if user-facing)
   - [ ] README updated (if new feature)
   - [ ] Configuration changes documented
   - [ ] Breaking changes noted

4. **Compliance Documentation** (if required)
   - [ ] Data handling documented
   - [ ] Security controls documented
   - [ ] Privacy impact documented

**VERDICT: APPROVE | BLOCK**
- APPROVE: Documentation complete
- BLOCK: Documentation missing

---

## FINAL DECISION

After all phases complete:

**IF ANY PHASE RETURNED BLOCK:**
- Report the blocking issues
- List required changes
- Do NOT proceed to commit

**IF ALL PHASES APPROVED:**
- Summarize changes made
- List files modified
- Suggest running `/preflight` before committing

---

## OUTPUT FORMAT

```markdown
## Implementation Summary

**Requirement:** <original requirement>

**Design Decision:** <@Architect summary>

**Changes Made:**
- File: <path>
  - <description of change>
- File: <path>
  - <description of change>

**Security Review:** @Security - <APPROVE/BLOCK>
<findings>

**Quality Review:** @QA - <APPROVE/BLOCK>
<findings>

**Documentation:** @Docs - <APPROVE/BLOCK>
<findings>

**Compliance:** @Compliance - <APPROVE/BLOCK>
<findings>

**Observability:** @Observability - <APPROVE/BLOCK>
<findings>

---

**OVERALL STATUS:** <APPROVED/BLOCKED>

**Next Steps:**
<If approved: suggest running /preflight>
<If blocked: list required fixes>
```

---

## RULES

1. **No shortcuts** - All phases must complete
2. **Surgical changes only** - Minimal edits to achieve goal
3. **Security first** - @Sentinel veto power
4. **Quality gate** - @QA validates all code changes
5. **Documentation** - @Scribe ensures auditability
6. **Fail fast** - Stop at first BLOCK, report clearly

## NON-NEGOTIABLES

From .agent/rules/global-compliance-requirements.mdc:
- No secrets in code
- No PII in logs
- Type hints required (Python)
- Tests for new endpoints
- HTTPS for external calls
- Input validation everywhere
- Proper error handling