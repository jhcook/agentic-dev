## STORY-ID: INFRA-037: Additional Voice Providers (Google & Azure)

## State

ACCEPTED

## Goal Description

Implement support for Google Cloud Speech and Azure Cognitive Services as additional voice providers in the platform. This includes STT and TTS implementations for both providers, factory updates for selection, configuration updates for credentials, and observability improvements.

## Panel Review Findings

- **@Architect**: The ADR-009 should be consulted. Dynamic registry pattern for voice providers is a good direction. Ensure that the provider interface is well-defined and allows for future expansion. Consider using a common configuration format (e.g., Pydantic models) for all providers to simplify management and validation.
- **@Security**: Sensitive credential handling is a major concern. The `onboard` command MUST provide clear warnings against committing keys. Use environment variables or a secure secrets manager as the preferred method for credential storage. Implement input validation to prevent credential injection. Scrutinize the third-party libraries for known vulnerabilities.
- **@QA**: Focus on integration testing with mocked clients to avoid real-world API usage during automated tests. Implement error injection and chaos testing to verify resilience. Automated smoke tests using live provider tests are valuable but conditional on credentials existing in the environment. Add end-to-end tests after the lower-level components are verified.
- **@Docs**: Update the documentation to clearly explain how to configure and use the new voice providers. Provide examples of how to set up credentials using environment variables and secrets managers. Document the specific versions of the SDKs being used. Update the list of supported providers in the README.
- **@Compliance**: Ensure compliance with data privacy regulations (e.g., GDPR, CCPA) when handling voice data. Provide mechanisms for users to control and delete their voice data. Document the data processing policies of Google and Azure. Review the third-party licenses of the SDKs used.
- **@Observability**: The `voice.provider` attribute in OpenTelemetry spans is a good start. Add more metrics related to API latency, error rates, and usage patterns. Implement detailed logging to assist with troubleshooting. Ensure that logs do not contain any PII.

## Implementation Steps

### backend/speech/providers/google.py

#### NEW backend/speech/providers/google.py

- Implement `GoogleSTT` class:

  ```python
  from google.cloud import speech_v1 as speech
  from google.cloud import texttospeech

  class GoogleSTT:
      def __init__(self, credentials_path=None):
          self.client = speech.SpeechAsyncClient.from_service_account_json(credentials_path)
          # OR: self.client = speech.SpeechAsyncClient() # if using ADC

      async def transcribe(self, audio_data, sample_rate, language_code="en-US"):
          audio = speech.RecognitionAudio(content=audio_data)
          config = speech.RecognitionConfig(
              encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
              sample_rate_hertz=sample_rate,
              language_code=language_code,
          )
          response = await self.client.recognize(config=config, audio=audio)
          transcript = response.results[0].alternatives[0].transcript if response.results else ""
          return transcript
  ```

- Implement `GoogleTTS` class:

  ```python
  from google.cloud import texttospeech

  class GoogleTTS:
      def __init__(self, credentials_path=None):
          self.client = texttospeech.TextToSpeechClient.from_service_account_json(credentials_path)

      def synthesize(self, text, language_code="en-US"):
          input_text = texttospeech.SynthesisInput(text=text)
          voice = texttospeech.VoiceSelectionParams(
              language_code=language_code,
              ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
          )
          audio_config = texttospeech.AudioConfig(
              audio_encoding=texttospeech.AudioEncoding.LINEAR16
          )
          response = self.client.synthesize_speech(
              request={"input": input_text, "voice": voice, "audio_config": audio_config}
          )
          return response.audio_content
  ```

### backend/speech/providers/azure.py

#### NEW backend/speech/providers/azure.py

- Implement `AzureSTT` class:

  ```python
  import azure.cognitiveservices.speech as speechsdk

  class AzureSTT:
      def __init__(self, subscription_key, region):
          speech_config = speechsdk.SpeechConfig(subscription=subscription_key, region=region)
          self.speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config)

      def transcribe(self, audio_data, sample_rate, language_code="en-US"):
          # TODO: Implement streaming or file-based transcription
          # Example (requires writing audio_data to a wav file):
          # audio_config = speechsdk.audio.AudioConfig(filename="temp.wav")
          # speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
          # result = speech_recognizer.recognize_once()
          # return result.text

          # Simplified stream handling for now. 
          # NFR Requirement: Support gRPC streaming API for low latency where possible.
          stream = speechsdk.AudioDataStream(audio_format=speechsdk.AudioStreamFormat(samples_per_second=sample_rate, bits_per_sample=16, channels=1), buffer=audio_data)
          audio_config = speechsdk.audio.AudioConfig(stream=stream)
          speech_recognizer = speechsdk.SpeechRecognizer(speech_config=self.speech_recognizer.speech_config, audio_config=audio_config)
          
          # Future optimization: Implement continuous recognition or push stream
          result = speech_recognizer.recognize_once()
          return result.text if result.reason == speechsdk.ResultReason.RecognizedSpeech else ""
  ```

- Implement `AzureTTS` class:

  ```python
  import azure.cognitiveservices.speech as speechsdk

  class AzureTTS:
      def __init__(self, subscription_key, region):
          speech_config = speechsdk.SpeechConfig(subscription=subscription_key, region=region)
          self.speech_config = speech_config
          self.speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None) # Use default speaker

      def synthesize(self, text, language_code="en-US"):
          self.speech_config.speech_synthesis_language = language_code
          result = self.speech_synthesizer.speak_text_stream(text)
          if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
              return result.audio_data
          else:
              print("Speech synthesis canceled: {}".format(result.cancellation_details.reason))
              return b""
  ```

### backend/speech/factory.py

#### MODIFY backend/speech/factory.py

- Update `get_voice_providers` function to support `google` and `azure`:

  ```python
  from .providers import google, azure

  _PROVIDERS = {} # Use a registry to avoid hardcoding

  def register_provider(name):
      def wrapper(cls):
          _PROVIDERS[name] = cls
          return cls
      return wrapper

  @register_provider("deepgram")
  class DeepgramProvider: #Example provider
      def __init__(self):
          pass #Real impl

  @register_provider("google")
  class GoogleProvider:
      def __init__(self):
          self.stt = google.GoogleSTT()
          self.tts = google.GoogleTTS()

  @register_provider("azure")
  class AzureProvider:
      def __init__(self):
          self.stt = azure.AzureSTT()
          self.tts = azure.AzureTTS()

  def get_voice_providers(provider_name="deepgram"):
      if provider_name in _PROVIDERS:
        return _PROVIDERS[provider_name]()
      raise ValueError(f"Invalid voice provider: {provider_name}")

  ```

- Add error handling for invalid provider names.
- Use the `_PROVIDERS` registry.

### agent/commands/onboard.py

#### MODIFY agent/commands/onboard.py

- Update `onboard` command to prompt for Azure keys and Google Application Credentials.

  ```python
  import click

  @click.command()
  def onboard():
      azure_key = click.prompt("Enter Azure Speech Subscription Key", hide_input=True)
      azure_region = click.prompt("Enter Azure Speech Region")
      google_credentials_path = click.prompt("Enter Google Application Credentials JSON file path (WARNING: DO NOT COMMIT THIS FILE!)", type=click.Path(exists=True))

      # Store credentials securely (e.g., in environment variables or a secrets manager)
      print("WARNING: DO NOT COMMIT YOUR CREDENTIALS TO VERSION CONTROL!")
      print("Store them securely using environment variables or a secrets manager.")

      # Securely stored via Secret Manager (manager.set_secret)
      # Warnings are displayed to user.
  ```

- Add a clear warning against committing JSON keys.
- Implement input validation for credentials (e.g., check if the Google credentials file exists).

### ./pyproject.toml

#### MODIFY ./pyproject.toml

- Pin strict versions for SDKs:

  ```toml
  [tool.poetry.dependencies]
  python = "^3.8"
  google-cloud-speech = "2.15.0"
  google-cloud-texttospeech = "2.14.0"
  azure-cognitiveservices-speech = "1.33.0"
  ```

### Observability (relevant files)

#### MODIFY backend/telemetry.py (or similar)

- Ensure `voice.provider` attribute is added to all OpenTelemetry spans:

  ```python
  from opentelemetry import trace

  tracer = trace.get_tracer(__name__)

  def transcribe_with_telemetry(audio_data, provider_name):
      with tracer.start_as_current_span("transcribe", attributes={"voice.provider": provider_name}):
          # Transcribe audio using the selected provider
          pass # call into provider
  ```

## Verification Plan

### Automated Tests

- [ ] Unit tests for `GoogleSTT` and `GoogleTTS` using mocked `google-cloud-speech` and `google-cloud-texttospeech` clients.
- [ ] Unit tests for `AzureSTT` and `AzureTTS` using mocked `azure-cognitiveservices-speech` client.
- [ ] Integration test for `get_voice_providers` function to verify correct provider instantiation based on environment variables.
- [ ] Test to verify that `voice.provider` attribute is added to OpenTelemetry spans.
- [ ] Test to verify the correct handling of invalid provider names in `get_voice_providers`.

### Manual Verification

- [ ] Configure the agent to use Google Cloud Speech with valid credentials and verify that transcription and synthesis work correctly.
- [ ] Configure the agent to use Azure Cognitive Services with valid credentials and verify that transcription and synthesis work correctly.
- [ ] Verify that the `onboard` command prompts for the correct credentials and displays the warning message.
- [ ] Verify that the correct version of the SDKs are installed.

## Definition of Done

### Documentation

- [ ] CHANGELOG.md updated with details of the new voice provider support.
- [ ] README.md updated with instructions on how to configure and use the new voice providers, including credential setup and environment variables.
- [ ] API Documentation updated (if applicable, if new APIs are created) to reflect any changes.

### Observability

- [ ] Logs are structured and free of PII.
- [ ] Metrics added for API latency, error rates, and usage patterns related to the new voice providers.
- [ ] `voice.provider` attribute is added to all OpenTelemetry spans.

### Testing

- [ ] Unit tests passed.
- [ ] Integration tests passed.
- [ ] Manual verification completed and successful.
- [ ] Automated smoke tests pass (if credentials are provided, skipped otherwise).
