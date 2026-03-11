# EXC-006: Temporary Exemptions for 500 LOC Ceiling

## Context
INFRA-106 introduces a strict 500 physical single-file LOC ceiling using `scripts/check_loc.py` enforced in pre-commit and preflight gates for CI.
However, several existing legacy monolithic files already break this ceiling limit before the LOC quality gating was put in force.

## Motivation
Immediate strict enforcement of the LOC limit across the whole existing codebase blocks merging all new work. It introduces significant, risky refactoring work to split large modules before new functionality can be merged down.

## Exemption List
The following files are granted a `# nolint: loc-ceiling` exemption and are permitted to remain over the 500 LOC limit as a stop-gap until the structural decomposition targeted by INFRA-099 is executed:

- `.agent/src/agent/core/fixer.py`
- `.agent/src/agent/core/utils.py`
- `.agent/src/agent/core/secrets.py`
- `.agent/src/agent/core/_governance_legacy.py`
- `.agent/src/agent/tui/app.py`
- `.agent/src/agent/commands/check.py`
- `.agent/src/agent/commands/gates.py`
- `.agent/src/agent/commands/secret.py`
- `.agent/src/agent/commands/journey.py`
- `.agent/src/agent/commands/implement.py`
- `.agent/src/agent/commands/lint.py`
- `.agent/src/agent/sync/sync.py`
- `.agent/src/agent/sync/notion.py`
- `.agent/src/agent/core/adk/tools.py`
- `.agent/src/agent/core/adk/orchestrator.py`
- `.agent/src/agent/core/ai/service.py`

## Conditions
1. Existing files should not continue tracking unbounded upwards in physical lines.
2. New non-migration code added must comply directly with the < 500 limit. 
3. Files must have these tags stripped when their refactoring drops them below the limit.
