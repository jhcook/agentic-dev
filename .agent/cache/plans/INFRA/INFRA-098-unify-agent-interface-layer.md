# INFRA-098: Unify Console and Voice Agent Interface Layer

This decomposition breaks **INFRA-098** into 8 manageable stories, ensuring each remains under the 400 LOC limit while progressively building the unified tool architecture.

### Decomposition Plan

1. **INFRA-139: Core Tool Registry & Foundation** (Registry API, Base classes)
2. **INFRA-140: Dynamic Tool Engine & Security** (AST scanning, hot-reload, custom directory)
3. **INFRA-141: Migration: Filesystem & Shell Modules** (Console tool migration + new file ops)
4. **INFRA-142: Migration: Search & Git Modules** (AST-aware search, git history, and diffs)
5. **INFRA-143: Migration: Project & Knowledge Modules** (Story/Runbook management, Vector search)
6. **INFRA-144: New Domains: Web, Testing, Deps & Context** (New capability expansion)
7. **INFRA-145: Interface Integration: Console & Voice Adapters** (Refactor sessions and orchestrator)
8. **INFRA-146: Cleanup & Deprecation** (LangChain decorator stripping, orchestrator cutover, audit logs)
9. **INFRA-183: Tool Registry Cutover — Retire LangChain Decorator Layer** *(Added post-INFRA-145)* (Full `@tool` removal, voice orchestrator cutover, OTel per-call spans)

---

### INFRA-098.1: Core Tool Registry & Foundation
**Description**: Establish the new `agent/tools/` package and the `ToolRegistry` class. Define the standard `Tool` interface that replaces both Console and LangChain patterns.
**LOC Estimate**: ~150 lines.
**AC Coverage**: Partial AC-1.
**Tasks**:
- Create `.agent/src/agent/tools/__init__.py` with `ToolRegistry`.
- Define `Tool` and `ToolResult` data classes.
- Implement `register()`, `get_tool()`, and `list_tools()` in the registry.
- Add `unrestrict_tool(name)` skeleton for permission elevation.

### INFRA-098.2: Dynamic Tool Engine & Security
**Description**: Migrate the dynamic tool creation logic from Voice to the centralized registry.
**LOC Estimate**: ~250 lines.
**AC Coverage**: AC-2, AC-7, Negative Test.
**Tasks**:
- Create `agent/tools/dynamic.py`.
- Port AST-based security scanner (rejecting `eval`, `subprocess` without `# NOQA`).
- Implement `create_tool` with `importlib` hot-reload.
- Configure `.agent/src/agent/tools/custom/` as the default output directory.

### INFRA-098.3: Migration: Filesystem & Shell Modules
**Description**: Port filesystem and shell tools from `agent/core/adk/tools.py` to the new registry structure and add new file operations.
**LOC Estimate**: ~350 lines.
**AC Coverage**: Partial AC-1, AC-8 (filesystem/shell parts).
**Tasks**:
- Create `agent/tools/filesystem.py`: `read`, `write`, `patch`, `delete`, plus new `move_file`, `copy_file`, `file_diff`.
- Create `agent/tools/shell.py`: `run_command`, `send_input`, `status`.
- Implement path validation and sandbox enforcement within these modules.

### INFRA-098.4: Migration: Search & Git Modules
**Description**: Implement code search and git management tools, including AST-aware symbol lookup.
**LOC Estimate**: ~300 lines.
**AC Coverage**: AC-8 (search/git parts).
**Tasks**:
- Create `agent/tools/search.py`: `grep`, `find_files`, `find_symbol` (AST), `find_references`.
- Create `agent/tools/git.py`: `show_diff`, `blame`, `file_history`, and basic commit/branch ops.

### INFRA-098.5: Migration: Project & Knowledge Modules
**Description**: Port tools related to story management and documentation/knowledge access.
**LOC Estimate**: ~250 lines.
**AC Coverage**: AC-8 (project/knowledge parts).
**Tasks**:
- Create `agent/tools/project.py`: `match_story`, `read_story`, `read_runbook`.
- Create `agent/tools/knowledge.py`: `read_adr`, `read_journey`, `search_knowledge` (vector interface).

### INFRA-098.6: New Domains: Web, Testing, Deps & Context
**Description**: Implement the brand-new tool modules for web access, testing, dependency management, and edit context.
**LOC Estimate**: ~380 lines.
**AC Coverage**: AC-8 (remaining parts).
**Tasks**:
- Create `agent/tools/web.py`: `fetch_url` (with markdown conversion).
- Create `agent/tools/testing.py`: `run_tests` (structured output).
- Create `agent/tools/deps.py`: `add_dependency`, `audit`.
- Create `agent/tools/context.py`: `checkpoint`, `rollback`.

### INFRA-098.7: Interface Integration: Console & Voice Adapters
**Description**: Refactor the existing agent sessions to consume tools from the new `ToolRegistry` instead of local implementations.
**LOC Estimate**: ~300 lines.
**AC Coverage**: AC-4, AC-3 (integration part).
**Tasks**:
- Refactor `.agent/src/agent/core/session.py` and TUI session to use the registry.
- Refactor `.agent/src/backend/voice/orchestrator.py` to use the registry.
- Update `.agent/src/agent/core/engine/executor.py` to fix blocking waits with "Thinking..." yields.

### INFRA-098.8: Cleanup & Deprecation
**Description**: Strip LangChain `@tool` decorators from voice tools, wire orchestrator to `ToolRegistry`,
and finalize audit logging. **Note**: `agent/core/adk/tools.py` is NOT deleted — it is the canonical
`ToolRegistry` implementation (coexistence decision from INFRA-145).
**LOC Estimate**: ~200 lines (decorator removal + orchestrator swap).
**AC Coverage**: AC-5, AC-6, Compliance NFR.
**Tasks**:
- Remove `@tool` decorators and `langchain_core.tools` imports from all `backend/voice/tools/` files.
- Update `backend/voice/tools/registry.py` to delegate to `ToolRegistry`.
- Replace `RunnableConfig` injection in `git.py`, `interactive_shell.py`, `fix_story.py`, `workflows.py`, `qa.py`.
- Implement standardized OpenTelemetry tracing and structured audit logging for tool execution.

### INFRA-098.9: Tool Registry Cutover — Retire LangChain Decorator Layer *(Added post-INFRA-145)*
**Description**: Debt retirement story added after INFRA-145 chose a coexistence strategy over full
deletion. Completes the migration of the voice agent's tool dispatch off LangChain `@tool` decorators
and onto `ToolRegistry`, retiring the remaining 42 decorators across 15 files.
**Story**: INFRA-183
**LOC Estimate**: ~50 lines net (mostly deletions).
**AC Coverage**: Completes original AC-5, AC-6 intent; adds AC-7 (OTel per-call spans).
**Tasks**:
- Strip 42 `@tool` decorators and 15 `from langchain_core.tools import tool` imports.
- Swap `backend/voice/tools/registry.py` to `ToolRegistry` delegation.
- Wire `backend/voice/orchestrator.py` tool binding to `ToolRegistry`.
- Remove `USE_UNIFIED_REGISTRY` feature flag from `agent/core/feature_flags.py`.
- Instrument `tool_security.py` to emit OTel span per tool call.
