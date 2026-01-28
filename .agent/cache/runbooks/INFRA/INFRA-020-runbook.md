# INFRA-020: Implement Agent Audit

## State
ACCEPTED

## Goal Description
Implement a comprehensive `agent audit` command that enables compliance officers and lead developers to execute a governance audit of the repository. The audit will assess traceability, identify stagnant code, and flag orphaned governance artifacts to generate actionable compliance reports. This feature ensures better oversight, transparency, and management of "Governance as Code."

---

## Panel Review Findings

- **@Architect**:
    - The feature aligns with architectural goals of traceability and compliance but introduces complexity in scanning logic.
    - Resource constraints (memory usage for large repos) require iterative/streaming processing. Benchmarking must confirm efficiency.
    - File-scanning logic must remain modular to reduce coupling if future governance standards evolve.
    - **Recommendation**: Follow architectural layers - `audit.py` in commands layer delegates to core helpers in `governance.py`. Create an Architectural Decision Record (ADR) to document design decisions, rationale, scalability, performance and the error handling strategy.

- **@Security**:
    - Logs and reports must not include sensitive information (private keys, PII, credentials).
    - Ensure `.auditignore` functionality mitigates scanning of confidential files.
    - Documentation must warn users to include sensitive files in `.auditignore`.
    - **Action**: Add `.auditignore` example in docs, ensure `scrub_sensitive_data` is applied. Include common directories like `.venv`, `node_modules`. Also, be sure the parsing of the ignore files is robust.

- **@QA**:
    - Complexity increases test case coverage requirements (date logic, traceability regexes).
    - False positives for "Ungoverned Files" could cause trust issues. Develop whitelist/blacklist strategies.
    - Sample repositories of diverse structures should be audited for comprehensive validation.
    - **Action**: Unit tests for date math, traceability logic; integration tests on this repo. Elaborate on whitelist/blacklist strategies and how these will be implemented (e.g., configuration files, CLI options).

- **@Docs**:
    - Extensive documentation required:
        - CLI commands and options (`--fail-on-error`, `--min-traceability`)
        - How to configure `.auditignore`
        - Report structure and interpretation
    - Consider visual examples for non-technical users.
    - **Action**: Add CLI docs to README, sample `.auditignore`, example `AUDIT-<Date>.md`.

- **@Compliance**:
    - Traceability and orphaned artifact rules well-defined. Must be clearly documented.
    - Provide resolution examples in `AUDIT-<Date>.md` reports.
    - Legal verification needed to ensure `.auditignore` isn't misused to bypass compliance. Schedule a meeting with legal counsel to review the intended use and potential for misuse of the `.auditignore` feature, especially concerning data relevant to SOC2 and GDPR compliance.
    - Ensure source code is contains license headers.

- **@Observability**:
    - Audit outcomes must be observable (metrics: scan duration, % untraceable files).
    - Errors must not crash the process but be logged for post-mortem analysis.
    - Structured JSON logging recommended for external tool consumption. Define thresholds that would cause a warning or alert.

- **@ProductOwner**:
    - Explicitly define user experience goals: How should the output of the audit look to different types of users (compliance officers vs. lead developers)? How quickly should the audit complete for repositories of varying sizes?
    -  Ensure legal provides explicit approval of the intended use of the `.auditignore` file.
    - Ensure that a plan is in place for supporting deprecated artifacts or old data in cache.
    - Double-check the proposed changes against global compliance requirements, especially around data minimization and purpose limitation.

- **@TechWriter**:
    - Implement a mechanism to allow users to customize the "traceability regexes" used to identify STORY/RUNBOOK references.
    - Ensure integration tests cover scenarios with different `.auditignore` configurations and various levels of untraceable/stagnant files.

- **@ComplianceOfficer**:
    - Implement an audit log that tracks modifications to the `.auditignore` file.
    - Make sure the compliance report outputted in the `AUDIT-<Date>.md` provides remediation steps that are actionable by specific teams, i.e. link to specific documentation, configuration, or code that needs to be addressed.
    - Add code to check for license headers to the audit.

- **@BackendLead**:
    - Use Pydantic models consistently for both serializing data to the report and deserializing configuration data (e.g., from `.auditignore`). If not already done, ensure you are using Pydantic V2 as it brings performance improvements. Ensure you update code accordingly.

---

## Implementation Steps

### Component 1: CLI Command Layer

#### [NEW] [audit.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/commands/audit.py)

Create new command following existing patterns (`lint.py`, `check.py`):

```python
# Key structure:
# - audit() function as typer command
# - Options: --fail-on-error, --min-traceability <int>, --stagnant-months <int>
# - Delegates to governance.run_audit() in core layer
# - Outputs AUDIT-<Date>.md report
```

**Implementation details**:
1. Typer command with options:
   - `--fail-on-error`: Exit non-zero if any issues found
   - `--min-traceability <int>`: Minimum % traceability required (default 80)
   - `--stagnant-months <int>`: Months threshold for stagnant code (default 6)
   - `--output <path>`: Custom output path for report
2. Load `.gitignore` and `.auditignore` patterns
3. Call core helpers for each scan type. Implement streaming or iterative processing for large repositories, using generators or asynchronous operations to avoid blocking the main thread.
4. Generate markdown report. Consider also providing an option to output in JSON format for easier parsing by external tools and automation. Also, use color indicators (✅/⚠️/❌) to highlight the severity of different findings.
5. Exit with appropriate code based on findings

---

### Component 2: Core Governance Layer

#### [MODIFY] [governance.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/core/governance.py)

Extend existing governance module with audit helpers:

```python
# New functions to add:

def is_governed(file_path: Path) -> Tuple[bool, Optional[str]]:
    """Check if file is traceable to a Story/Runbook."""
    # Check file headers for STORY-XXX / RUNBOOK-XXX references
    # Check agent_state.db for file->story mappings
    
def find_stagnant_files(repo_path: Path, months: int = 6) -> List[Dict]:
    """Find files not modified in X months with no active story link."""
    # Use git log to get last commit date per file
    # Filter by age threshold
    # Exclude files linked to active stories
    
def find_orphaned_artifacts(cache_path: Path, days: int = 30) -> List[Dict]:
    """Find OPEN stories/plans with no activity in X days."""
    # Scan .agent/cache/stories and .agent/cache/plans
    # Check State/Status fields
    # Exclude items blocked by dependencies
    
def run_audit(
    repo_path: Path,
    min_traceability: int = 80,
    stagnant_months: int = 6,
    ignore_patterns: List[str] = None
) -> AuditResult:
    """Run full governance audit and return structured results."""
```

**Data structure**:
```python
@dataclass
class AuditResult:
    traceability_score: float
    ungoverned_files: List[str]
    stagnant_files: List[Dict]  # {path, last_modified, days_old}
    orphaned_artifacts: List[Dict]  # {path, state, last_activity}
    errors: List[str]  # Any permission/access errors encountered
```

Ensure that the `is_governed` function prioritizes one source of truth (e.g., file headers) and uses the other as a fallback for consistency. Also, consider the implications of identifying "stagnant files" under GDPR. If these files contain PII, ensure that the audit process flags files exceeding data retention policies, regardless of whether they are actively governed. Add a check to `find_stagnant_files` to check for PII and compare the last modified date with retention policies. Consider adding a grace period or configurable threshold to avoid flagging artifacts that are merely temporarily inactive for 'orphaned artifacts'. This prevents false positives and reduces alert fatigue.

---

### Component 3: Report Generation

#### [NEW] [formatters.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/core/formatters.py) (extend if exists)

Add report formatter:

```python
def format_audit_report(result: AuditResult) -> str:
    """Generate AUDIT-<Date>.md markdown report."""
    # Health scores with color indicators (✅/⚠️/❌)
    # Top 10 worst offenders tables
    # Summary section for non-technical stakeholders
```

---

### Component 4: CLI Integration

#### [MODIFY] [main.py](file:///Users/jcook/repo/agentic-dev/.agent/src/agent/main.py)

Register the new audit command:

```python
from agent.commands import audit
app.command("audit")(audit.audit)
```

---

### Component 5: Documentation

#### [MODIFY] [README.md](file:///Users/jcook/repo/agentic-dev/.agent/README.md)

Add `agent audit` CLI usage section. Highlight the purpose of the audit command, the types of issues it detects (traceability, stagnant code, orphaned artifacts), and links to more detailed documentation.

#### [NEW] .auditignore (example)

```
# Files excluded from governance audit
legacy/**
vendor/**
*.generated.*
# Common sensitive data patterns
*.key
*.pem
password=
```

Provide comprehensive examples covering various scenarios (e.g., excluding specific files, directories, patterns).  Clearly explain how the `.auditignore` file interacts with `.gitignore` and any precedence rules. The implementation should handle both `.auditignore` and `.gitignore` files gracefully, likely with `.auditignore` taking precedence. Ensure this precedence is clearly documented. Expand the documentation for `.auditignore` to include specific examples for common sensitive data patterns (e.g., API keys, database passwords, common PII fields). This will help users avoid unintentional exposure of sensitive information during audits. Also, be sure to include common directories like `.venv`, `node_modules`, and other dependency installation locations.

---

## Verification Plan

### Automated Tests

#### Unit Tests

File: `.agent/tests/unit/test_audit.py`

```bash
# Run with:
PYTHONPATH=.agent/src pytest .agent/tests/unit/test_audit.py -v
```

- [ ] `test_is_governed_with_story_header`: File with `STORY-XXX` header returns governed=True
- [ ] `test_is_governed_without_header`: File without header returns governed=False
- [ ] `test_find_stagnant_files_date_math`: Correctly identifies files older than threshold. Add unit tests specifically for edge cases in date math (e.g., leap years, different timezones)
- [ ] `test_find_stagnant_files_excludes_active`: Files linked to active stories excluded
- [ ] `test_find_orphaned_artifacts`: Correctly identifies OPEN artifacts with no activity
- [ ] `test_find_orphaned_excludes_blocked`: Items blocked by dependencies excluded
- [ ] `test_auditignore_patterns`: Verify `.auditignore` patterns are respected. Enhance the `test_auditignore_patterns` to test nested directories and more complex patterns. Also, add tests specifically to ensure that the `.auditignore` file is correctly parsed and applied. Add/test with nested directories in the ignore file, for example, `test_auditignore_nested_directories`. Add a unit test that runs the audit on an empty repository to ensure it handles this scenario gracefully (e.g., returns a zero score without errors).

#### Integration Tests

File: `.agent/tests/integration/test_audit_integration.py`

```bash
# Run with:
PYTHONPATH=.agent/src pytest .agent/tests/integration/test_audit_integration.py -v
```

- [ ] `test_audit_on_current_repo`: Run on this repo, verify report structure
- [ ] `test_min_traceability_flag`: Test `--min-traceability` triggers failure appropriately. Add an integration test that modifies the minimum traceability threshold (`--min-traceability`) to different values (e.g., 0, 50, 100) and asserts the correct number of ungoverned files are reported.
- [ ] `test_fail_on_error_exit_code`: Verify non-zero exit with `--fail-on-error` when issues found
- [ ] Create or use multiple sample repositories with different structures and governance practices for integration testing. This will help catch false positives and ensure the audit tool works effectively across various projects.
- [ ] Develop integration tests that specifically target GDPR and SOC2 compliance scenarios. For example, create a test case that uploads a file containing PII, runs the audit, and verifies that the PII is properly flagged and redacted in the report.
- [ ] Include test cases that simulate the misuse of `.auditignore` to ensure that the audit tool can detect attempts to bypass compliance checks.
- [ ] Add tests to verify that migrations succeed and that data is migrated correctly (if applicable).

### Manual Verification

- [ ] Run `agent audit` on this repo and verify:
  - Report generates at `AUDIT-<Date>.md`
  - Health scores are reasonable. Add more explicit guidance on what qualifies as “reasonable” health scores.
  - Report is readable by non-technical stakeholders
- [ ] Manually create an ungoverned file and verify it appears in report
- [ ] Test `--min-traceability 100` fails on any real repo
- [ ] Run performance tests on large repositories.

---

## Definition of Done

### Documentation
- [ ] CLI usage in `.agent/README.md`
- [ ] Example `.auditignore` documented
- [ ] Sample `AUDIT-<Date>.md` in `docs/examples/`
- [ ] CHANGELOG.md updated. Be specific about what kind of changes should be listed in the CHANGELOG. Indicate whether each change is a feature, fix, or breaking change.
- [ ] API Docs (OpenAPI): While this feature doesn't directly expose a REST API, consider documenting the command's functionality and options within the broader architectural documentation. This helps maintain a comprehensive view of the agent's capabilities.

### Observability
- [ ] Logs provide tracebacks for non-critical errors
- [ ] Audit metrics logged (duration, file counts). These metrics should be useful for monitoring and troubleshooting. Define specific metrics to be logged (e.g., number of files scanned, number of ungoverned files, scan duration). Ensure structured logging includes enough context (e.g., repository path, audit parameters) to facilitate debugging.
- [ ] Structured JSON logging for scan results

### Testing
- [ ] 80%+ code coverage for governance audit logic
- [ ] Integration tests pass
- [ ] All existing tests continue to pass
- [ ] Add clear criteria for code maintainability in the Definition of Done.

Following these architectural guidelines will help ensure that the `agent audit` command is robust, scalable, maintainable, and compliant with governance requirements.
