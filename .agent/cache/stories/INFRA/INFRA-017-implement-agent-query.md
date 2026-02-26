# INFRA-017: Implement Agent Query

## State
COMMITTED

## Problem Statement
Finding specific information in a large, governed agentic codebase is difficult. Developers often have questions like "Where is the logic for X defined?" or "How do I create a new workflow?" that would require reading multiple markdown files or grep searching code. There is no central, natural-language interface to query the repository's knowledge base (Docs, ADRs, Code).

### Scope: Ollama Provider Integration
This commit adds Ollama as a self-hosted local AI provider to the AIService, enabling the `agent query` command (and all other AI-powered commands) to use a local LLM. Changes include `service.py` (provider registration, health check, completion), `config.py` (valid providers), and `router.py` (tier alias).

## User Story
As a developer, I want to use a local, self-hosted LLM (Ollama) for all agent commands, so that I can work offline, ensure data privacy, and avoid API costs.

## Acceptance Criteria
- [x] **Provider Registration**: Ollama is registered as a valid provider in `config.py` and routed via `router.py` (tier alias).
- [x] **Health Check**: `AIService.reload()` performs an HTTP health check against the Ollama endpoint before marking it available.
- [x] **Completion**: `AIService._try_complete()` calls Ollama via the OpenAI-compatible API with correct message format.
- [x] **Security Guard**: `OLLAMA_HOST` is restricted to localhost (`127.0.0.1`, `localhost`, `::1`) to prevent data exfiltration.
- [x] **Null-Safety**: `_try_complete()` guards against `None` content from Ollama responses.
- [x] **CLI Documentation**: All `--provider` help text includes `ollama` as a valid choice.
- [x] **Temperature Control**: `complete()` and `_try_complete()` accept an optional `temperature` parameter, propagated to all providers.
- [x] **Observability**: Ollama provider calls include an OpenTelemetry span (`ai.completion`) and latency histogram (`ai_completion_latency_seconds`).
- [x] **Deterministic Governance**: Gatekeeper mode uses `temperature=0.0` for reproducible findings; diff-scope constraint prevents flagging pre-existing issues.

### Deferred (Original agent query ACs)
- [ ] Context Retrieval via Smart Keyword Search
- [ ] AI Synthesis with RAG
- [ ] Citations in responses
- [ ] Conversation History (`--chat` flag)

## Non-Functional Requirements
- **Latency**: Answers should be generated within 5-10 seconds.
- **Performance**: context building should use `asyncio` for parallel file reading.
- **Cost**: Context window usage should be optimized (truncate large files).
- **Accuracy**: The model should refuse to answer if the context is insufficient, rather than hallucinating.

## Linked ADRs
- ADR-038 (Ollama Local Provider Integration)

## Linked Journeys
- JRN-016
- JRN-013

## Impact Analysis Summary
Components touched: `agent/core/ai/service.py` (provider registration, health check, completion, OTel span, temperature param), `agent/core/config.py` (valid providers), `agent/core/router.py` (tier alias), `agent/core/governance.py` (temperature=0, diff-scope constraint, diff-hunk validator), `agent/commands/{check,match,runbook,workflow,journey,implement,voice}.py` (--provider help text), `agent/tests/core/test_ai_service.py` (Ollama unit tests), `ADR-038-ollama-local-provider-integration.md` (architectural decision), `CHANGELOG.md` (feature entry), `README.md` (provider docs).
Workflows affected: Developer Productivity / AI Provider Selection / Governance Determinism.
Risks identified: Data Exfiltration (mitigated by localhost guard), Governance Non-Determinism (mitigated by temperature=0 and diff-scope constraint).

## Test Strategy
- **Unit Tests** (`test_ai_service.py`):
  - `test_ollama_health_check_success`: Mocks successful HTTP health check, asserts Ollama client is created.
  - `test_ollama_health_check_failure`: Mocks connection refused, asserts provider is skipped gracefully.
  - `test_ollama_security_guard_blocks_remote`: Sets `OLLAMA_HOST` to remote URL, asserts client is NOT created.
  - `test_ollama_temperature_passthrough`: Asserts `temperature=0.0` is forwarded to Ollama SDK call.
  - `test_ollama_null_safety`: Mocks `None` content from Ollama, asserts empty string returned.
  - `test_fallback_chain_reaches_ollama`: Verifies fallback chain reaches ollama after upstream failures.
  - Existing tests: `test_fallback_logic`, `test_metrics_increment`, `test_rate_limit_retry_backoff` (all updated for temperature kwarg).
- **Manual Verification**:
  - Run `agent preflight` multiple times to verify deterministic findings.
  - Test Ollama provider with `--provider ollama` on any command.

## Rollback Plan
- Revert service.py, config.py, router.py changes; remove ollama from valid providers.

## Copyright

Copyright 2026 Justin Cook
