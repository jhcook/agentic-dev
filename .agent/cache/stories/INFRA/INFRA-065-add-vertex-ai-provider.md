# INFRA-065: Add Vertex AI Provider to Agent CLI

## State

COMMITTED

## Problem Statement

The current Agent CLI, which solely relies on the Gemini (AI Studio) provider, suffers from rate limiting issues when used with multiple parallel agents, hindering performance and scalability for users requiring higher throughput.

## User Story

As a Google Cloud Platform user, I want to configure the Agent CLI to use Vertex AI as an alternative provider, so that I can leverage higher rate limits and improve the performance and scalability of my agent workflows in a production environment.

## Acceptance Criteria

- [ ] **Scenario 1**: Given `GOOGLE_CLOUD_PROJECT` is set and `provider: vertex` in `agent.yaml`, the CLI uses Vertex AI with ADC for API calls.
- [ ] **Scenario 2**: Given `GEMINI_API_KEY` is set and `provider: gemini` in `agent.yaml`, the CLI uses AI Studio for API calls.
- [ ] **Scenario 3**: Given neither credential is set, the CLI displays a clear, actionable error instructing the user to configure either provider.
- [ ] **Scenario 4**: Given both `GEMINI_API_KEY` and `GOOGLE_CLOUD_PROJECT` are set, the explicit `provider` value in `agent.yaml` takes precedence.
- [ ] **Condition**: `config.py` includes `"vertex"` in `get_valid_providers()`.
- [ ] **Condition**: `credentials.py` validates `GOOGLE_CLOUD_PROJECT` when `provider: vertex`.
- [ ] **Condition**: `agent.yaml` supports `provider: vertex` alongside `provider: gemini`.
- [ ] **Condition**: Extract shared `genai.Client` construction into a factory to avoid duplication between `gemini` and `vertex` branches.
- [ ] **Error Handling**: ADC failures (expired credentials, missing `gcloud auth application-default login`) surface clear, actionable messages — not raw `google.auth` tracebacks.
- [ ] **Error Handling**: Vertex path must NOT silently fall back to `generativelanguage.googleapis.com` on ADC failure — it must fail hard.
- [ ] **Observability**: Log active provider and endpoint at startup: `"Provider: vertex (aiplatform.googleapis.com, project=X, location=Y)"`.
- [ ] **Observability**: Log provider, model, and retry count on rate-limit errors (429).
- [ ] **Documentation**: Update `getting_started.md` with side-by-side provider comparison and Vertex AI setup instructions (ADC, env vars, API enablement).
- [ ] **Negative Test**: Invalid provider names in `agent.yaml` produce a graceful error.

## Non-Functional Requirements

- **Performance**: Vertex AI provides significantly higher rate limits than AI Studio, supporting parallel ADK agent execution.
- **Security**: Vertex AI uses short-lived OAuth2 tokens via ADC — no long-lived API keys in memory. `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` logged at DEBUG level only (not INFO) to avoid leaking project IDs in public CI logs.
- **Compliance**: Vertex AI data processing governed by GCP ToS/DPA. Apache 2.0 license headers on all new/modified files.
- **Observability**: Structured log entries on provider fallback events: `{"event": "provider_fallback", "from": "vertex", "to": "gemini", "reason": "..."}`.

## Linked ADRs

- None

## Linked Journeys

- None

## Impact Analysis Summary

Components touched: `service.py`, `config.py`, `credentials.py`, `agent.yaml`, `getting_started.md`
Workflows affected: All CLI workflows using AI providers (`panel`, `preflight`, `implement`, `commit`, `query`).
Risks identified: ADC misconfiguration (expired tokens, missing `gcloud auth`); project ID not set; Vertex AI API not enabled in GCP project.

## Test Strategy

- **Unit**: Mock `genai.Client` constructor — test both `vertexai=True` and `api_key=` paths without hitting real APIs.
- **Unit**: `validate_credentials()` passes when `GOOGLE_CLOUD_PROJECT` is set for `vertex` provider, fails when missing.
- **Edge case**: `provider: vertex` with `GOOGLE_CLOUD_PROJECT` unset — verify clear error, not obscure SDK failure.
- **Edge case**: ADC credentials expired — verify actionable error message.
- **Edge case**: ADC token refresh under `asyncio.gather()` (3-slot semaphore) — verify thread safety.
- **Integration**: `env -u VIRTUAL_ENV uv run agent panel --panel-engine adk` with Vertex AI completes without 429 errors.

## Rollback Plan

Revert changes to `service.py`, `config.py`, `credentials.py`, and `agent.yaml`. The `gemini` provider remains fully functional as the default fallback.
