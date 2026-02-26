# ADR-038: Ollama Local Provider Integration

## Status

ACCEPTED

## Context

The agent CLI relies on cloud-hosted LLMs (Gemini, OpenAI, Anthropic) for all AI-powered commands. Developers need the ability to run commands offline, ensure data privacy for sensitive codebases, and avoid API costs during local development. Ollama provides a self-hosted, OpenAI-compatible API for running open-source models locally.

## Decision

Ollama is integrated as a first-class provider in `AIService` by reusing the existing OpenAI Python SDK client with Ollama's OpenAI-compatible `/v1/` endpoint. Key decisions:

1. **Client Reuse**: Use `openai.OpenAI(base_url="{OLLAMA_HOST}/v1")` instead of introducing a new SDK dependency. This leverages existing tested infrastructure.
2. **Security Guard**: `OLLAMA_HOST` is validated to only allow localhost addresses (`127.0.0.1`, `localhost`, `::1`). Remote hosts are rejected to prevent accidental data exfiltration.
3. **Health Check**: A lightweight HTTP `GET /` health check runs during `reload()` to confirm Ollama is available before registering the client. Failure is graceful (provider is skipped).
4. **Router Tier Alias**: Ollama is registered in the router as the lowest-priority fallback in the chain: `gh → gemini → vertex → openai → anthropic → ollama`.
5. **Temperature Control**: A `temperature` parameter was added to `complete()` and `_try_complete()` for all providers to support deterministic governance mode (`temperature=0`).
6. **Observability**: All provider calls are wrapped with an OpenTelemetry span (`ai.completion`) and a latency histogram (`ai_completion_latency_seconds`), both defined at the `complete()` level to ensure uniform coverage.

## Alternatives Considered

- **Dedicated Ollama SDK**: Would add a new dependency and diverge from existing patterns. Rejected in favor of OpenAI-compatible API reuse.
- **Docker-based Provider**: Would add operational complexity. Rejected because Ollama's native install is simpler for developers.
- **LiteLLM Proxy**: Would unify all providers behind one abstraction but adds a runtime dependency. Deferred for future consideration.

## Consequences

- Positive:
  - Developers can work fully offline with local models.
  - No API costs during local development.
  - Data never leaves the developer's machine.
  - Minimal new code — reuses OpenAI client infrastructure.
- Negative:
  - Local model quality varies by hardware and model size.
  - Health check adds ~2s to initialization when Ollama is unreachable.
  - Developers must install and manage Ollama separately.

## Copyright

Copyright 2026 Justin Cook
