# INFRA-010: Enhance Implement Command

## Parent Plan
INFRA-008

## State
COMMITTED

## Problem Statement
The `env -u VIRTUAL_ENV uv run agent implement` command currently only generates advice as Markdown. It does not help the developer by actually applying the changes, which reduces the "agentic" value.

## User Story
As a developer, I want to run `env -u VIRTUAL_ENV uv run agent implement <RUNBOOK_ID> --apply` so that the agent automatically modifies the files as per the runbook.

## Acceptance Criteria
- [ ] `env -u VIRTUAL_ENV uv run agent implement` accepts an `--apply` flag.
- [ ] When `--apply` is used, the agent parses code blocks from the AI response.
- [ ] The agent applies the changes to the file system.
- [ ] The agent prompts for confirmation before writing files (unless `--yes` is passed).

## Impact Analysis Summary

**Components Touched:**
- `agent/commands/implement.py` - Major changes (3 new functions, enhanced main function, 6 new imports)
- `README.md`, `CHANGELOG.md` - Documentation updates

**Workflows Affected:**
- Implementation Workflow - Developers can now auto-apply code changes
- Development Velocity - Reduces manual copy-paste work
- Backup/Recovery - New `.agent/backups/` directory created

**Risks:**
- **Security (LOW)**: File writes protected by confirmation prompts; backups enable rollback
- **Performance (LOW)**: Regex parsing and file I/O are synchronous
- **Reliability (MEDIUM)**: AI code quality depends on model accuracy; mitigated by user confirmation
- **Path Traversal (LOW)**: Uses `Path()` normalization but no explicit validation

**Breaking Changes:** None - backward compatible, new flags are optional

## Test Strategy
- Create a dummy runbook.
- Run `env -u VIRTUAL_ENV uv run agent implement --apply`.
- Verify file changes are applied correctly.
