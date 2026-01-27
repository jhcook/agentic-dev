# Agentic Voice Backend

This repository contains the backend services for the Agentic Voice application.

## Features

- **Voice Agent**: A fully capable voice assistant with bi-directional audio, VAD, and secure tools. [Documentation](docs/features/voice-agent.md)
- **Governance**: Automated preflight checks.

## Getting Started

1. **Clone the repository:**
2. **Onboard:** Run `agent onboard` to set up dependencies and credentials.

## Voice Configuration

The Agent supports multiple voice providers for Speech-to-Text (STT) and Text-to-Speech (TTS).

### Supported Providers

- **Deepgram** (Default): Cloud-based streaming STT/TTS.
- **Azure Speech Services**: High-quality cloud voice. Requires `AZURE_PASSWORD` (stored in secrets).
- **Google Cloud Speech**: Requires Service Account JSON (encrypted in secrets).
- **Local/Whisper**: Offline support (beta).

### Configuration

For detailed configuration (including how to switch providers in `voice.yaml`), see [Backend Voice Documentation](.agent/docs/backend_voice.md#configuration).

### Setup

Run the onboarding wizard to configure providers securely:

```bash
agent onboard
```

This command will prompt for necessary API keys and securely store them in the project's encrypted Secret Manager. **Never commit raw keys or JSON files.**

## Privacy & Compliance (GDPR/SOC2)

- **Data Retention**: Voice data sent to cloud providers (Google/Azure) is transient and processed only for the requested transcription/synthesis. This application *does not* store user audio or transcripts persistently unless explicitly configured for debugging (which is disabled by default in production).
- **PII Handling**: Avoid speaking PII. While the providers are enterprise-grade and SOC2 compliant, this application treats voice data as sensitive. Logs are sanitized to exclude full transcripts in production.
- **User Rights (Deletion)**:
  - **Local Data**: Use `rm -rf .agent/logs/*` to delete all local session logs.
  - **Cloud Data**: Data sent to Google/Azure via API is typically not retained for training by default (refer to Google Cloud data logging and Azure Cognitive Services privacy policies). Consumers can opt-out of logging in their respective cloud consoles.
- **Credentials**: All provider credentials are encrypted at rest using the internal Secret Manager. Managed Identities should be used for production deployments on Azure/GCP.
- **Third-Party Licenses**:
  - `google-cloud-speech` (Apache 2.0)
  - `google-cloud-texttospeech` (Apache 2.0)
  - `azure-cognitiveservices-speech` (MIT)
  - All SDKs are compatible with this project's license.

## Agent Management Console

Start the visual dashboard (Frontend + Backend) with a single command:

```bash
agent admin start
```

This launches:

- **Backend API**: `http://127.0.0.1:8000`
- **Frontend UI**: `http://127.0.0.1:8080`

The frontend is configured to proxy API requests to the backend automatically.

> **Note**: The frontend source code is located in `.agent/web/`.
