# EXC-001: `update_story_state` Location in CLI Layer

## Status
Accepted

## Challenged By
@Architect

## Rule Reference
`commit-workflow.mdc` — @Architect: *"Move `update_story_state` back to `agent/core/utils.py`. The function is core to state management and does not belong in the CLI layer."*

## Affected Files
- `.agent/src/agent/commands/utils.py` (canonical location)
- `.agent/src/agent/commands/workflow.py` (caller)
- `.agent/src/agent/commands/implement.py` (caller)

## Original Finding

> Move `update_story_state` back to `agent/core/utils.py`. The function is core to state management and does not belong in the CLI layer. Revert the changes to tests, using `Path.exists` correctly. Explain the reasoning for the change in comments.

## Justification

`update_story_state` is **not core domain logic** — it is a CLI-layer file-system utility that:

1. **Writes to markdown files** on disk (`story_file.write_text()`), which is a CLI-workflow artefact concern, not a domain model operation.
2. **Prints Rich-formatted output** via `rich.console.Console`, coupling it to the CLI presentation layer.
3. **Triggers Notion sync** by importing and calling `agent.sync.sync.push_safe` — an external side-effect that has no place in a core utility module.

Placing this function in `core/utils.py` violates **separation of concerns** by coupling the core utility layer to:
- `rich` (CLI presentation)
- `agent.sync.sync` (external I/O / third-party integration)

Both callers are CLI commands:
- `agent commit` (`commands/workflow.py`) — sets state to `COMMITTED`
- `agent implement` (`commands/implement.py`) — sets state to `IN_PROGRESS`

`core/utils.py` should remain **importable without pulling in sync or Rich dependencies**, consistent with `lean-code.mdc`: *"Do not introduce dependencies unless absolutely required"* and *"Prefer explicitness over magic — avoid hidden side effects."*

## Conditions

Re-evaluate this exception if:
- `update_story_state` needs to be called from a non-CLI context (e.g. API endpoint, background worker)
- The core/commands dependency boundary is refactored
- `core/utils.py` adopts Rich or sync dependencies for other reasons

## Consequences

- **Positive**: `core/utils.py` remains lightweight and side-effect free. Clear dependency direction: `commands` → `core`, never the reverse.
- **Negative**: "State management" logic is split: `find_story_file` lives in `core/utils.py`, but `update_story_state` lives in `commands/utils.py`. Developers must know to look in two places.
