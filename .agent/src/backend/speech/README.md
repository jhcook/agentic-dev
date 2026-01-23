# Voice Provider Architecture

This module implements a provider-agnostic voice architecture using the `STTProvider` and `TTSProvider` interfaces.

## Overview

The core logic interacts with voice services through strict interfaces defined in `interfaces.py`, ensuring that vendor-specific code is isolated.

## Components

- **`interfaces.py`**: Defines `STTProvider` and `TTSProvider` protocols.
- **`providers/`**: Contains concrete implementations of the providers.
  - `deepgram.py`: Implementation using the Deepgram SDK.
- **`factory.py`**: Provides a `get_voice_providers()` function to load the configured provider based on environment variables.

## Configuration

The following environment variables are supported:

- `VOICE_PROVIDER`: The name of the provider to use (default: `deepgram`).
- `DEEPGRAM_API_KEY`: Required if `VOICE_PROVIDER` is `deepgram`.

## Adding a New Provider

1. Create a new file in `providers/` (e.g., `openai.py`).
2. Implement a class that satisfies `STTProvider` and/or `TTSProvider`.
3. Update `factory.py` to support the new provider name in `SUPPORTED_PROVIDERS` and add the instantiation logic.
