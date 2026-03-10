# Contributing

We welcome contributions from the community! Thank you for helping us improve the project.

## Development Setup

The fastest way to set up your development environment is with our onboarding command. This ensures all required tools and configurations are in place.

1.  **Fork and clone the repository:**

## Adding a New AI Provider

If you wish to add support for a new AI backend (e.g. LLaMA, OpenAI), please use the Strategy standard enforced by our AI Layer:
1. Navigate to `.agent/src/agent/core/ai/providers.py`.
2. Author your custom strategy class (e.g. `NewProvider`) ensuring it explicitly inherits from the standard `AIProvider` Protocol.
3. Decorate your generic `stream` or `generate` request outputs with `@ai_retry` from `core/ai/streaming.py` to inherit platform rate-limit protections and telemetry logs.
4. Register your provider implementation with `ProviderRegistry.register()`.