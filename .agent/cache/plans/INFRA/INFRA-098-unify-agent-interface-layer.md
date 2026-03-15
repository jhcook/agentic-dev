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
8. **INFRA-146: Cleanup & Deprecation** (Legacy removal, LangChain stripping, Audit logs)

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
**Description**: Remove legacy tool files, strip LangChain dependencies, and finalize audit logging.
**LOC Estimate**: ~200 lines (excluding deletions).
**AC Coverage**: AC-5, AC-6, Compliance NFR.
**Tasks**:
- Delete `.agent/src/agent/core/adk/tools.py`.
- Delete `.agent/src/backend/voice/tools/` directory.
- Remove all `langchain_core.tools` imports and `@tool` decorators from migrated logic.
- Implement standardized OpenTelemetry tracing and structured audit logging for tool execution and elevation.
