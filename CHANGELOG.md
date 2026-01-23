# Changelog

## [Unreleased]

### Added
- Introduced a provider-agnostic voice architecture with `STTProvider` and `TTSProvider` interfaces.
- Implemented a concrete `Deepgram` provider for speech-to-text and text-to-speech services.
- Added a factory function to load voice providers based on environment configuration.