# AI Service Layer Architecture

The system utilizes a modular Strategy pattern to provide interchangeable AI interfaces to the runtime agent. 

## Structure
The core AI layer exists within `.agent/src/agent/core/ai` and is decoupled into discrete segments:
- **service.py**: The facade that orchestrates commands and interacts with downstream workflows.
- **protocols.py**: Provides the static `typing.Protocol` interfaces and custom exception wrappers (`AIRateLimitError`, `AIConnectionError`) that guarantee all unified models expose identical APIs.
- **providers.py**: Serves as the factory layer containing the concrete implementations (e.g., `AnthropicProvider`, `OpenAIProvider`, `VertexAIProvider`, `MockProvider`), as well as the dynamic `_PROVIDER_REGISTRY` which permits fast local-model onboarding.
- **streaming.py**: Houses all `async` stream ingestion wrappers alongside resiliency decorators like `ai_retry` which implement standard exponential backoff.

For instructions on adding new AI Provider models, please see `CONTRIBUTING.md`.


## Copyright

Copyright 2026 Justin Cook
