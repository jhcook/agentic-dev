# INFRA-033: Enable MCP Tool Use for Agent Councils

## State

ACCEPTED

## Goal Description

This task aims to enhance the intelligence and functionality of Agent Councils (e.g., Preflight Council, Governance Panel) by enabling them to autonomously leverage MCP tools like `github:get_issue` or `filesystem:read_file`. This capability will allow the agents to perform deeper, context-aware analysis by dynamically interacting with the environment, rather than relying solely on static git diffs. It ensures the agents can engage in a "Reason -> Act -> Observe" loop to generate more accurate recommendations or verification outcomes.

## Panel Review Findings

(See above for full panel findings - Verified as consistent with local simulation)

## Implementation Steps

### 1. Engine & Configuration (INFRA-034 Dependency)

*Note: The Core Loop logic is built in INFRA-034. This runbook focuses on wiring it into the Councils.*

#### [MODIFY] `agent/core/config.py`

- Add schema support for `agent.councils.<name>.tools` (List[str]).
- Add default allow-lists (e.g., `preflight` = `['github:get_issue', 'filesystem:read_file']`).

### 2. Governance Integration

#### [MODIFY] `agent/core/governance.py` (`convene_council`)

- Update `convene_council_full` to:
    1. Check `agent.yaml` for tool configuration for the current council.
    2. If tools enabled, instantiate `AgentExecutor` (from `agent.core.engine`).
    3. Inject tool definitions into the System Prompt.
    4. Run the `executor.run()` loop instead of `ai_service.complete()`.

### 3. Security Hardening

#### [MODIFY] `agent/core/engine.py` (or wherever loop lives)

- Ensure `SecureManager` scrubs all observation outputs.

## Verification Plan

### Automated Tests

- [ ] **Integration**: `tests/core/test_governance.py` - Mock `AgentExecutor` and verify `convene_council` calls it correctly when tools are configured.
- [ ] **Security**: Verify sensitive data in mock tool output is scrubbed before next prompt.

### Manual Verification

- [ ] Run `env -u VIRTUAL_ENV uv run agent panel` on a branch with a known GitHub issue reference.
- [ ] Verify logs show: `Tool Call: github:get_issue` -> `Observation: ...` -> `Final Answer`.
