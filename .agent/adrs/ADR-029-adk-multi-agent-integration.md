# ADR-029: ADK Multi-Agent Integration for Governance Panel

## State

ACCEPTED

## Context

The AI Governance Council runs sequential LLM calls per role — one prompt per role, iterated over chunked diffs. This works but has limitations:

1. **No tool use**: Roles cannot inspect the codebase, read ADRs, or validate their findings against actual files.
2. **No delegation**: If the Architect spots a security concern, it cannot ask the Security agent to investigate.
3. **No iteration**: Roles get one shot at analysis with no ability to refine findings.
4. **Vendor lock-in risk**: The legacy panel prompt format is tightly coupled to the prompt engineering expectations of specific models.

Google's Agent Development Kit (ADK) provides multi-agent orchestration with tool use, delegation, and iteration out of the box, solving all four limitations.

## Decision

**Integrate ADK as an opt-in orchestration engine for the governance panel.**

### Key design choices

1. **ADK wraps AIService**: The `AIServiceModelAdapter` bridges our synchronous `AIService.complete()` to ADK's async `BaseLlm` interface via `asyncio.run_in_executor()`. This preserves vendor agnosticism — any provider configured in the CLI (Gemini, OpenAI, Anthropic, GitHub CLI) works with ADK agents.

2. **Sync-to-async bridge**: The CLI is synchronous (ADR-028, Typer). We use `asyncio.run()` as the entry point, and `run_in_executor()` to move blocking `AIService.complete()` calls off the event loop. A `threading.Lock()` guards the singleton to prevent interleaved provider state.

3. **Read-only tool whitelist**: Exactly 5 tools are exposed — `read_file`, `search_codebase`, `list_directory`, `read_adr`, `read_journey`. All paths are validated against `repo_root` to prevent traversal. No write or network tools.

4. **Feature flag**: Engine selection is via `agent.yaml` (`panel.engine: adk`) or CLI flag (`--panel-engine adk`). Default is `legacy`.

5. **Graceful fallback**: If `google-adk` is not installed, or if the ADK engine raises any exception (`ImportError`, `TimeoutError`, generic `Exception`), the system falls back to the legacy sequential panel with an install suggestion.

6. **Audit log parity**: ADK panel output uses the same JSON structure and markdown log format as the legacy panel for SOC 2 compliance.

## Alternatives Considered

- **LangGraph**: Already a dependency, but its graph-based approach adds complexity for what is fundamentally a fan-out/aggregate pattern. ADK's `LlmAgent` with `sub_agents` is a more natural fit.
- **CrewAI**: Not a Google-supported framework. Adds an opinionated abstraction layer we don't need.
- **Direct multi-threading**: Would require reimplementing tool use, iteration limits, and delegation from scratch.

## Consequences

- **Positive**: Governance agents can now validate findings against actual codebase files, reducing false positives.
- **Positive**: Vendor-agnostic — all existing AI providers work without modification.
- **Positive**: Opt-in with zero breaking changes — legacy panel is the default.
- **Negative**: Adds `google-adk` as a transitive dependency (when opted in), bringing `google-genai` and related packages.
- **Negative**: `asyncio.run()` in a sync CLI creates a new event loop per invocation, which is slightly wasteful but acceptable for a CLI tool.

## References

- ADR-025: Lazy AI Service Initialization
- ADR-028: Typer Synchronous CLI Architecture
- [Google ADK Documentation](https://google.github.io/adk-python/)
