This decomposition breaks INFRA-170 into 5 manageable child stories, focusing on CLI behavior, deterministic gates, and modularization of the legacy governance and implementation logic.

### Decomposition Plan

1.  **INFRA-170-01: CLI Defaults and Contextual New-Story**: Updates command flags and enhances the `new-story` prompt with file tree context.
2.  **INFRA-170-02: Quality Gates and Syntax Validation**: Implements deterministic LOC/function length checks and the AI claim cross-validator.
3.  **INFRA-170-03: Governance Decomposition - Part A (Orchestration & Prompts)**: Initializes the `governance/` package and migrates the Panel and Prompt logic from `_governance_legacy.py`.
4.  **INFRA-170-04: Governance Decomposition - Part B (Validation & Reporting)**: Migrates finding validation and report formatting logic, completing the removal of `_governance_legacy.py`.
5.  **INFRA-170-05: Implement Command Refactor**: Decomposes the monolithic `implement.py` into focused sub-modules.

---

### INFRA-170-01: CLI Defaults and Contextual New-Story

**Description**
Modify the CLI entry points for `check` and `implement` to favor thorough analysis and update `new-story` to provide better context to the AI during decomposition planning.

**Acceptance Criteria**
- [ ] `agent check` and `agent preflight` default to `thorough=True`.
- [ ] `--quick` flag added to `agent check` and `agent preflight` to set `thorough=False`.
- [ ] `agent implement` defaults to thorough mode.
- [ ] `agent new-story` logic updated to fetch the current file tree (excluding ignored paths) and inject it into the story decomposition prompt.

**Impact Analysis**
- `.agent/src/agent/commands/check.py`: Change default argument values; add `--quick` flag.
- `.agent/src/agent/commands/implement.py`: Change default argument values; add `--quick` flag.
- `.agent/src/agent/commands/new_story.py`: Add logic to call `git ls-files` or similar to get the tree and append to the prompt context.

---

### INFRA-170-02: Quality Gates and Syntax Validation

**Description**
Implement deterministic code quality gates and a mechanism to verify AI-reported syntax errors using local Python tools.

**Acceptance Criteria**
- [ ] Create `governance/complexity.py` with AST-based LOC and function length counters.
- [ ] Implementation of **WARN** at >500 LOC per file in the diff.
- [ ] Implementation of **WARN** at 21–50 lines per function, **BLOCK** at >50 lines.
- [ ] Create `governance/syntax_validator.py` that uses `py_compile` or `pytest --collect-only` to verify files identified as "broken" by the AI.
- [ ] AI findings that claim syntax errors are auto-dismissed if the local validator passes.

**Impact Analysis**
- `.agent/src/agent/core/governance/complexity.py`: [NEW] Logic for file/function length gates.
- `.agent/src/agent/core/governance/syntax_validator.py`: [NEW] Logic for cross-validating AI claims vs `py_compile`.
- `.agent/src/agent/commands/check.py`: Integration of these new gates into the preflight execution flow.

---

### INFRA-170-03: Governance Decomposition - Part A (Orchestration & Prompts)

**Description**
Begin the decomposition of the 1,956 LOC `_governance_legacy.py` by moving the core orchestration and prompt generation logic into a new package.

**Acceptance Criteria**
- [ ] Create `.agent/src/agent/core/governance/__init__.py`.
- [ ] Extract the "Council" orchestration loop (the main panel logic) into `governance/panel.py`.
- [ ] Extract all system prompt templates and prompt building logic into `governance/prompts.py`.
- [ ] Update imports in the agent core to point to the new modular structure.

**Impact Analysis**
- `.agent/src/agent/core/governance/panel.py`: [NEW] Panel orchestration extracted from legacy.
- `.agent/src/agent/core/governance/prompts.py`: [NEW] Prompt templates extracted from legacy.
- `.agent/src/agent/core/_governance_legacy.py`: Removal of ~800 lines of code.

---

### INFRA-170-04: Governance Decomposition - Part B (Validation & Reporting)

**Description**
Complete the decomposition of `_governance_legacy.py` by moving validation logic and reporting structures into their own modules, then removing the legacy file.

**Acceptance Criteria**
- [ ] Extract finding validation logic into `governance/validation.py`.
- [ ] Extract report formatting, JSON assembly, and output logic into `governance/reports.py`.
- [ ] Ensure `governance/panel.py` integrates all sub-modules (complexity, syntax, validation, reports).
- [ ] Delete `.agent/src/agent/core/_governance_legacy.py`.
- [ ] Existing tests in `.agent/tests/governance/` pass without modification (or with only import updates).

**Impact Analysis**
- `.agent/src/agent/core/governance/validation.py`: [NEW] Logic for validating findings against source.
- `.agent/src/agent/core/governance/reports.py`: [NEW] Logic for generating the final quality report.
- `.agent/src/agent/core/_governance_legacy.py`: DELETED.

---

### INFRA-170-05: Implement Command Refactor

**Description**
Decompose the monolithic `implement.py` (1000+ LOC) into focused sub-modules to improve maintainability and satisfy complexity gates.

**Acceptance Criteria**
- [ ] Create `.agent/src/agent/commands/implement/` directory.
- [ ] Extract planning logic into `implement/planner.py`.
- [ ] Extract file writing and modification logic into `implement/writer.py`.
- [ ] Extract context gathering logic into `implement/context.py`.
- [ ] `agent implement` command remains the entry point but delegates to the new sub-modules.

**Impact Analysis**
- `.agent/src/agent/commands/implement.py`: Refactor to a delegator pattern (~150 LOC).
- `.agent/src/agent/commands/implement/planner.py`: [NEW] Strategy/Plan generation.
- `.agent/src/agent/commands/implement/writer.py`: [NEW] File system operations.
- `.agent/src/agent/commands/implement/context.py`: [NEW] Gathering repository context for implementation.