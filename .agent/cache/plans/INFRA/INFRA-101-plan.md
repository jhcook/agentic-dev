# Plan: Governance Module Decomposition

The monolithic `core/governance.py` (1,988 LOC) will be decomposed into a structured package `core/governance/`. To maintain the <400 LOC per child story limit, the panel orchestration logic is split into prompt assembly and execution logic.

## Child Stories

### INFRA-101.1: Extract Role and Persona Management
- **Description**: Migrate role-loading and persona mapping logic from `core/governance.py` to `core/governance/roles.py`.
- **Scope**: ~250 LOC.
- **Tasks**:
    - Implement `load_roles`, `get_role`, and persona mapping from `agents.yaml`.
    - Implement `@Security`, `@Architect`, etc., resolution helpers.
    - Add negative tests for missing/malformed `agents.yaml`.
    - Create `tests/core/governance/test_roles.py`.

### INFRA-101.2: Extract Validation and Audit Logging
- **Description**: Migrate preflight gate execution and audit logging to `core/governance/validation.py`.
- **Scope**: ~350 LOC.
- **Tasks**:
    - Implement `run_preflight`, `log_governance_event`, `log_skip_audit`, and `GateResult` aggregation.
    - Ensure SOC2 fields (`resource_id`, `story_id`, `timestamp`) are present in all logging calls.
    - Implement `scrub_sensitive_data` preservation.
    - Create `tests/core/governance/test_validation.py`.

### INFRA-101.3: Extract Panel Prompt Assembly Helpers
- **Description**: Move council-convening prompt construction and helper utilities to `core/governance/panel_prompts.py`.
- **Scope**: ~300 LOC.
- **Tasks**:
    - Extract internal prompt formatting and template logic used by `convene_council_full`.
    - Implement PEP-484 type hints and PEP-257 docstrings for all internal helpers.
    - Add unit tests for prompt structure and variable injection.

### INFRA-101.4: Implement Council Orchestration Logic
- **Description**: Implement the primary council execution functions in `core/governance/panel.py`.
- **Scope**: ~350 LOC.
- **Tasks**:
    - Implement `convene_council_full` and `convene_council_fast` using helpers from `.roles` and `.panel_prompts`.
    - Integrate OpenTelemetry spans for orchestration performance monitoring.
    - Create `tests/core/governance/test_panel.py`.

### INFRA-101.5: Governance Package Integration and Facade
- **Description**: Finalize the `core/governance/` package by establishing the public API and removing the legacy module.
- **Scope**: ~150 LOC.
- **Tasks**:
    - Create `core/governance/__init__.py` with `__all__` re-exports for backward compatibility.
    - Delete the monolithic `core/governance.py`.
    - Verify behavioral equivalence with existing `tests/core/test_governance.py`.
    - Run circular import check: `python -c "import agent.cli"`.