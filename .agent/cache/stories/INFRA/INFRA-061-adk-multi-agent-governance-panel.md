# INFRA-061: ADK Multi-Agent Governance Panel

## State

IN_PROGRESS

## Problem Statement

The governance panel in `convene_council_full` is a sequential prompt loop: it iterates over roles, calls `ai_service.complete()` once per role with a static system prompt, parses the structured VERDICT/FINDINGS output, and aggregates results. This architecture has three fundamental limitations:

1. **No tool use**: Roles can't inspect the codebase, run linters, or query the DB — they only see the diff text pasted into the prompt.
2. **No delegation**: The Architect can't ask the Security role to deep-dive on a finding. Each role is isolated.
3. **No iteration**: If a role's findings are ambiguous, there's no loop to refine — one shot per role per chunk.

Google ADK provides exactly the primitives to solve this: `LlmAgent` with tool bindings, hierarchical agent delegation, and built-in agent loops with termination conditions.

## User Story

As a **developer governed by the agent framework**, I want the governance panel to use real multi-agent orchestration so that each role can use tools, delegate to other roles, and refine its analysis iteratively — producing higher-quality, more accurate governance reviews.

## Acceptance Criteria

- [ ] **AC-1**: Add `google-adk>=1.0.0` as an optional dependency under `[project.optional-dependencies] adk = [...]` in `pyproject.toml`. No `google-cloud-*` or Vertex AI packages are added.
- [ ] **AC-2**: `AIServiceModelAdapter` wraps `AIService.complete(system, user)` holistically via `loop.run_in_executor()`, treating the entire service (including provider fallback logic in `try_switch_provider()`) as a black box. The adapter does NOT call individual providers. This preserves vendor agnosticism — ADK never knows which provider is used.
- [ ] **AC-3**: Each governance role in `agents.yaml` maps to an ADK `Agent` with system instruction, focus area, and tools. Agent factory: `create_role_agent(role: Dict, tools: List) -> Agent`. Fields mapped: `role` → agent name, `description` + `governance_checks` → system instruction, `instruction` → appended context.
- [ ] **AC-4**: Role agents have 5 read-only tools: `read_file(path)`, `search_codebase(query)`, `list_directory(path)`, `read_adr(id)`, `read_journey(id)`. All path-accepting tools validate `Path.resolve().is_relative_to(config.repo_root)`. Tools are **explicitly** passed to each agent — no ADK default tool bindings (which may include HTTP/write tools).
- [ ] **AC-5**: A `GovernanceCoordinator` agent delegates to role sub-agents, collects findings, and synthesizes the final VERDICT/SUMMARY/FINDINGS/REQUIRED_CHANGES output.
- [ ] **AC-6**: Role agents can request deeper analysis from sibling agents via ADK delegation (e.g., Architect asks Security to investigate a dependency).
- [ ] **AC-7**: Role agents loop (max 3 iterations) to refine vague findings before finalizing their verdict.
- [ ] **AC-8**: `convene_council_full` dispatches to `_convene_council_adk()` or `_convene_council_legacy()` based on `panel.engine` config read from `agent.yaml` (under `panel:` section), defaulting to `legacy`. Uses `config.load_yaml(config.etc_dir / "agent.yaml").get("panel", {}).get("engine", "legacy")` or a new `config.panel_engine` property. Note: `Config` has no generic `get()` — AC references the dotted-key pattern, not a direct method call.
- [ ] **AC-9**: Fallback covers: `ImportError` (ADK not installed), `asyncio.TimeoutError`, ADK-specific exceptions (e.g., `google.adk.AgentError`), and generic `Exception`. Each produces a distinct warning. Fallback message says: `pip install 'agent[adk]'`.
- [ ] **AC-10**: The ADK panel respects existing `_filter_relevant_roles()` — skipped roles don't get instantiated as agents. Filtered role list is passed to the orchestrator factory.
- [ ] **AC-11**: CLI flag `agent preflight --panel-engine adk` overrides config per-invocation for testing.
- [ ] **AC-12**: Thread safety: `AIServiceModelAdapter` uses `threading.Lock()` to serialize concurrent LLM calls through the `AIService` singleton (module-level at `service.py:728`). Document that this negates parallelism benefits initially; `_ensure_initialized()` and `try_switch_provider()` mutate shared state.
- [ ] **AC-13**: Async event loop: `_convene_council_adk()` uses `asyncio.run()` at the top of the function, wrapping the entire orchestration. NOT inside individual agent calls. Per ADR-028, CLI is synchronous — validate no nested `asyncio.run()` from providers.
- [ ] **AC-14**: Each tool invocation has a 10-second timeout. No write or network tools are permitted.
- [ ] **AC-15**: OpenTelemetry spans: `adk.coordinator` (top-level with `panel.engine` attribute), `adk.agent.{role_name}` (per-agent with `verdict`, `findings_count`, `tool_calls_count`, `error` boolean), `adk.tool.{tool_name}` (per-invocation).
- [ ] **AC-16**: Write **ADR-029** documenting: (1) why ADK over alternatives (LangGraph, CrewAI), (2) sync-to-async bridge rationale, (3) thread safety trade-offs accepted, (4) vendor agnosticism guarantee.
- [ ] **AC-17**: `search_codebase(query)` implementation defined: delegates to `subprocess.run(["rg", "--json", query, repo_root], timeout=10)` with fallback to in-process `grep`. Output capped at 50 matches.
- [ ] **AC-18**: ADK panel produces identical audit log format (`governance-{story_id}-{timestamp}.md`) as legacy. Divergence breaks SOC 2 evidence collection.
- [ ] **AC-19**: Transitive dependency audit: run `pip install google-adk && pip list | wc -l` before merge. Verify no GPL/AGPL transitive deps. Document in ADR-029.
- [ ] **AC-20**: Coordinator delegation test: Architect delegates to Security → Security returns findings → coordinator includes both role outputs.
- [ ] **AC-21**: Max-iterations guard test: agent reaches 3-iteration cap → finalizes with current findings (no infinite loop).
- [ ] **AC-22**: Console displays runtime: `[dim]⏱️ Panel completed in {N}s (engine: adk|legacy)[/dim]`.
- [ ] **Negative Test**: With `panel.engine: legacy`, the old sequential loop is used unchanged.
- [ ] **Negative Test**: Missing `google-adk` with `panel.engine: adk` emits `pip install 'agent[adk]'` suggestion and falls back to legacy.

## Non-Functional Requirements

- Performance: Parallel agent execution should complete ≤1.5x legacy runtime for equivalent workloads. Accept serial execution initially due to `AIService` singleton lock; optimize in follow-up.
- **Vendor agnostic**: ADK is the orchestration layer only — it manages tools, delegation, and loops. Model calls are routed through `AIServiceModelAdapter`, which delegates to `AIService` for provider selection, API keys, and fallback logic. Adapter wraps `complete()` holistically — ADK never interacts with individual providers.
- Zero lock-in: No Google Cloud SDK, Vertex AI, or `google-cloud-*` packages are added. The only new dependency is `google-adk` itself (Apache 2.0 licensed — compatible with project license).
- Observability: ADK agent traces with LLM call attribution per-role for cost tracking. Benchmark metric `panel.runtime_ms` with `engine: adk|legacy` attribute. Future marker: per-role token count tracking (`adk.agent.{role_name}.total_tokens`).
- Backward compatibility: All existing tests, configs, and outputs remain valid. Feature flag defaults to `legacy`.
- Security: All tools read-only. Path scoping to repo root via `config.repo_root`. No network access from tools. ADK default tool bindings explicitly excluded. `google-adk` transitive deps audited for CVEs and license compatibility before merge.
- Audit log parity: ADK panel produces identical `governance-{story_id}-{timestamp}.md` format as legacy. SOC 2 evidence collection must not break.
- Parity definition: Legacy vs ADK parity tests compare *structure* (JSON schema valid, verdict in {PASS, BLOCK}, findings is list), not *content*. ADK agents with tools may produce better findings — content comparison is a benchmark, not a gate.

## Panel Advice Applied

- @Architect: New package `agent/core/adk/` with `adapter.py`, `agents.py`, `tools.py`, `orchestrator.py`, `compat.py`. Adapter wraps `AIService.complete()` holistically — not individual providers. `_filter_relevant_roles()` output passed to orchestrator factory. ADK tools are internal to `adk/` package; MCP tools via `get_council_tools()` remain separate.
- @QA: Parity tests compare *structure* (schema valid, verdict valid), not *content* (LLM nondeterminism). Separate fallback tests per error type (`ImportError`, `TimeoutError`, `AgentError`, generic). Added `test_coordinator_delegation()` and `test_agent_max_iterations()`. Tool unit tests use `tmp_path` fixtures, not real filesystem.
- @Security: Explicit tool whitelist (5 read-only tools) — no ADK default bindings. Path validation via same `Path.resolve().is_relative_to(config.repo_root)` pattern from INFRA-059. `search_codebase()` uses `subprocess.run` with `timeout=10`. Transitive dep audit required before merge. `threading.Lock()` justified: `AIService` singleton at `service.py:728` has mutable state in `_ensure_initialized()` and `try_switch_provider()`.
- @Product: Feature flag in `agent.yaml` under `panel:` section (`engine: adk|legacy`). `Config` class has no generic `get()` — use `load_yaml()` + `get_value()` or add `config.panel_engine` property. Fallback message says `pip install 'agent[adk]'`. Console displays `⏱️ Panel completed in {N}s (engine: adk|legacy)`.
- @Backend: Adapter implementation: `_sync_complete()` wraps `ai_service.complete()` under `threading.Lock()`, called via `loop.run_in_executor(None, ...)`. `asyncio.run()` at top of `_convene_council_adk()` only. `create_role_agent()` maps: `role` → name, `description` + `governance_checks` → instruction, `instruction` → context.
- @Observability: Hierarchical spans: `adk.coordinator` (with `panel.engine` attribute) → `adk.agent.{role_name}` (with `error` boolean) → `adk.tool.{tool_name}`. Future: per-role token counts for cost attribution.
- @Docs: ADR-029 documents: why ADK (vs LangGraph, CrewAI), sync-to-async bridge, thread safety trade-offs, vendor agnosticism guarantee. CHANGELOG: `### Added` — Multi-agent governance panel via Google ADK (opt-in). Install docs: `pip install 'agent[adk]'`.
- @Compliance: `google-adk` is Apache 2.0 — compatible. Transitive deps checked for GPL/AGPL. No new external data flows. Audit log format parity required for SOC 2.
- @Mobile / @Web: No impact — orchestration-only change. Role instructions and governance checks preserved through ADK migration.

## Linked ADRs

- ADR-005 (AI-Driven Governance Preflight)
- ADR-028 (Synchronous CLI Design)
- ADR-029 (ADK Multi-Agent Integration) — [TO BE WRITTEN]

## Linked Journeys

- JRN-033 (Governance Council Tool Suite)
- JRN-045 (Governance Hardening)
- JRN-055 (ADK Multi-Agent Panel Review)

## Impact Analysis Summary

Components touched:

- `pyproject.toml` — add `google-adk>=1.0.0` optional dependency under `[adk]` extras
- `.agent/src/agent/core/adk/` — [NEW] package with `adapter.py`, `agents.py`, `tools.py`, `orchestrator.py`, `compat.py`
- `.agent/src/agent/core/governance.py` — add `_convene_council_adk()` dispatch, extract current loop (lines 304-494) to `_convene_council_legacy()`
- `.agent/src/agent/core/config.py` — add `panel.engine` config read from `agent.yaml` (`panel:` section). Note: `Config` class has `get_value(data, key)` but no `get()` — need new accessor or property.
- `.agent/src/agent/core/ai/service.py` — no changes, but `AIService` singleton (line 728) is wrapped by adapter. `complete()` (line 321) and `try_switch_provider()` (line 293) called under lock.
- `.agent/etc/agents.yaml` — optional `tools` field per role
- `.agent/etc/agent.yaml` — add `panel:` section with `engine: legacy` default
- `.agent/adrs/ADR-029-adk-multi-agent-integration.md` — [NEW] architecture decision record

Workflows affected:

- `/preflight` — uses ADK panel when configured via `panel.engine: adk` or `--panel-engine adk`
- `/panel` — consultative mode uses ADK agents when configured

Risks identified:

- ADK adapter complexity (sync ↔ async): **High**. Mitigated by wrapping `complete()` holistically; start with `run_in_executor` + lock.
- ADK version instability: Medium. Pin to specific version; isolate behind adapter.
- Parallelism negated by AIService lock: Medium. Accept serial initially; optimize in follow-up. Document in ADR-029.
- Prompt explosion with tool context: Medium. Keep tools minimal (5 max); scope instructions tightly.
- Backward compatibility regression: Medium. Feature flag defaults to `legacy`; structural parity tests.
- Transitive dependency risk: Medium. Audit `google-adk` dep tree for CVEs and license conflicts before merge.
- Audit log divergence: Medium. ADK panel must produce identical format or SOC 2 evidence breaks.

## Test Strategy

- Unit: `test_adk_adapter_sync_provider()` — `AIServiceModelAdapter` bridges sync `complete()` via `run_in_executor`. Verifies fallback logic preserved.
- Unit: `test_adk_adapter_async_provider()` — native async providers work without executor bridge.
- Unit: `test_role_agent_creation()` — agents created from `agents.yaml` with correct instructions. Verifies `role` → name, `description` + `governance_checks` → instruction mapping.
- Unit: `test_tool_path_validation()` — path traversal is rejected with `ValueError`. Uses `tmp_path` fixtures.
- Unit: `test_tool_timeout()` — tool invocation respects 10s timeout.
- Unit: `test_search_codebase()` — `search_codebase(query)` returns capped results (≤50 matches) via `rg` subprocess.
- Unit: `test_backward_compatibility()` — `convene_council_full` falls back to legacy when ADK not installed.
- Unit: Coordinator aggregates role verdicts correctly (any BLOCK = overall BLOCK).
- Unit: `test_coordinator_delegation()` — Architect delegates to Security → Security returns findings → coordinator includes both.
- Unit: `test_agent_max_iterations()` — agent reaches 3-iteration cap → finalizes with current findings (no infinite loop).
- Unit: `test_thread_lock_serialization()` — 3 agents sending concurrent `complete()` calls → verify serialization (no interleaved outputs) and no deadlocks.
- Unit: `test_fallback_importerror()` — `ImportError` when ADK missing → falls back to legacy with install suggestion.
- Unit: `test_fallback_timeout()` — `asyncio.TimeoutError` during ADK execution → falls back to legacy.
- Unit: `test_fallback_agent_error()` — ADK-specific `AgentError` → falls back to legacy.
- Unit: `test_fallback_generic_exception()` — generic `Exception` → falls back to legacy.
- Unit: `test_explicit_tool_whitelist()` — agents receive exactly 5 tools, no ADK defaults.
- Parity: Same input → structurally equivalent output (JSON schema valid, verdict in {PASS, BLOCK}, findings is list). Content differences expected and acceptable.
- Integration: `convene_council_full` with `panel.engine: adk` produces valid structured output with identical audit log format.
- Integration: Fallback to legacy when `google-adk` not importable.
- Benchmark: Compare ADK vs legacy panel runtime for a standard 3-role changeset. Target ≤1.5x.

## Rollback Plan

- Set `panel.engine: legacy` in `agent.yaml` (instant rollback, no code changes).
- CLI override: `agent preflight --panel-engine legacy`.
- Remove `google-adk` from optional dependencies if needed.
- `governance.py` retains the legacy path indefinitely as the fallback.
- Audit log format identical — no evidence collection disruption.
