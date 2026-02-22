# INFRA-002: Workflow Token Optimization

Status: ACCEPTED

## Goal Description
Refactor Agent workflows to act as thin wrappers around Python CLI commands to reduce token usage and improve deterministic execution. Relocate configuration files to `.agent/etc/`, create standard AI instructions (`GEMINI.md`), and ensure specific commands (`new-runbook`, `commit`, `pr`) are optimized for Agent-Driven workflows.

## Panel Review Findings
- **@Architect**:
  - The separation of concerns (Workflows = Pointers, Python = Logic) is sound.
  - Relocating `agents.yaml` and `router.yaml` to `.agent/etc/` aligns with standard *nix configuration patterns.
  - Ensure `ContextLoader` correctly handles the new paths.

- **@Security**:
  - Reducing reliance on external AI for basic operations (like creating a file scaffold) is a security win (less data egress).
  - Ensure `env -u VIRTUAL_ENV uv run agent commit` with `-m` flags allows bypassing AI for sensitive commits if needed.
  
- **@QA**:
  - Verify that `env -u VIRTUAL_ENV uv run agent new-runbook` can fail gracefully if AI is unavailable (or properly handled by Agent intervention).
  - Test `env -u VIRTUAL_ENV uv run agent commit -m` to ensure it skips the interactive prompt.
  
- **@Docs**:
  - `GEMINI.md` and `copilot-instructions.md` are critical for ensuring future Agents understand this new structure.
  - Keep `task.md` and `walkthrough.md` updated.

## Implementation Steps

### Workflow & CLI Refactor
#### [MODIFY] [workflow.py]
- Implement `commit` command updates (add `-m` flag).
- Completed.

#### [MODIFY] [agent.py]
- All commands should support --ai and --provider  options
where it adds value, e.g., new-runbook et al.
- If provider is not provided it defaults to the default provider.
- If the default provider does not work, e.g., 429, it should fallback to the next provider if available.

#### [MODIFY] [runbook.py]
- Update `new_runbook` to support scaffold generation or robust AI fallback.
- (Note: Current CLI enforces AI, manual generation is the workaround).

#### [MODIFY] [Workflows]
- Update `workflows/runbook.md` to instruct Agent-Driven generation.
- Update `workflows/commit.md` to instruct Agent-Driven commit messages.
- Update `workflows/pr.md` to wrapper mode.

### Configuration Relocation
#### [MOVE] [Config Files]
- Move `agents.yaml` and `router.yaml` into `.agent/etc/`.
- Update `config.py` to reflect new paths.

### Documentation
#### [NEW] [AI Instructions]
- Create `GEMINI.md`.
- Create `.github/copilot-instructions.md`.

## Verification Plan
### Automated Tests
- [ ] Run `env -u VIRTUAL_ENV uv run agent new-runbook --help` to verify command availability.
- [ ] Run `env -u VIRTUAL_ENV uv run agent commit --help` to verify `-m` flag.

### Manual Verification
- [ ] Execute `workflows/runbook.md` process (this document).
- [ ] Verify `GEMINI.md` exists and contains correct paths.
- [ ] Verify `.agent/etc/agents.yaml` exists.

## Definition of Done
### Documentation
- [x] CHANGELOG.md updated
- [ ] README.md updated (if applicable)

### Observability
- [x] Logs are structured and free of PII

### Testing
- [ ] Unit tests passed
