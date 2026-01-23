import asyncio
import logging
import time

from deepgram import DeepgramClient
from prometheus_client import Counter, Histogram
from opentelemetry import trace

from backend.speech.interfaces import STTProvider, TTSProvider

logger = logging.getLogger(__name__)

# Metrics
VOICE_REQUESTS = Counter(
    "voice_provider_requests_total",
    "Total number of voice provider requests",
    ["provider", "type", "status"]
)
VOICE_LATENCY = Histogram(
    "voice_provider_request_duration_seconds",
    "Latency of voice provider requests",
    ["provider", "type"]
)
VOICE_ERRORS = Counter(
    "voice_provider_errors_total",
    "Total number of voice provider errors",
    ["provider", "type", "error_type"]
)

tracer = trace.get_tracer(__name__)

class ConfigurationError(Exception):
    pass

class DeepgramSTT(STTProvider):
    """Deepgram implementation for Speech-to-Text with Observability."""
    def __init__(self, api_key: str):
        if not api_key:
            raise ConfigurationError("Deepgram API key is not configured.")
        self.client = DeepgramClient(api_key=api_key)
        self.provider_name = "deepgram"

    async def listen(self, audio_data: bytes) -> str:
        with tracer.start_as_current_span("deepgram.stt.listen") as span:
            start_time = time.time()
            status = "success"
            try:
                # Extract correlation ID from current span
                span_ctx = span.get_span_context()
                correlation_id = format(span_ctx.trace_id, "032x")
                span.set_attribute("correlation_id", correlation_id)
                
                logger.info("Sending STT request to Deepgram.", extra={"provider": self.provider_name, "correlation_id": correlation_id})
                
                # Deepgram SDK v5 transcribe_file is synchronous
                # Run it in a thread pool to avoid blocking the event loop
                response = await asyncio.to_thread(
                    self.client.listen.v1.media.transcribe_file,
                    request=audio_data,
                    model="nova-2",
                    smart_format=True
                )
                
                # Best-effort transcription selection
                transcript = response.results.channels[0].alternatives[0].transcript
                logger.info("Received STT response from Deepgram.", extra={"provider": self.provider_name, "correlation_id": correlation_id})
                return transcript
                
            except Exception as e:
                status = "error"
                VOICE_ERRORS.labels(provider=self.provider_name, type="stt", error_type=type(e).__name__).inc()
                logger.error(f"Deepgram STT failed: {e}", extra={"provider": self.provider_name, "error": str(e), "correlation_id": correlation_id})
                span.record_exception(e)
                raise
            finally:
                duration = time.time() - start_time
                VOICE_REQUESTS.labels(provider=self.provider_name, type="stt", status=status).inc()
                VOICE_LATENCY.labels(provider=self.provider_name, type="stt").observe(duration)

    async def health_check(self) -> bool:
        """Checks API key validity by making a lightweight call (e.g. usage) or just assuming valid if client init."""
        # Deepgram doesn't have a dedicated 'ping' endpoint in SDK easily accessible without cost?
        # For now, we assume if client is init, it's okay, or try a list projects call if available.
        # Simple check:
        return True

class DeepgramTTS(TTSProvider):
    """Deepgram implementation for Text-to-Speech with Observability."""
    def __init__(self, api_key: str):
        if not api_key:
            raise ConfigurationError("Deepgram API key is not configured.")
        self.client = DeepgramClient(api_key=api_key)
        self.provider_name = "deepgram"

    async def speak(self, text: str) -> bytes:
        with tracer.start_as_current_span("deepgram.tts.speak") as span:
            start_time = time.time()
            status = "success"
            try:
                # Extract correlation ID from current span
                span_ctx = span.get_span_context()
                correlation_id = format(span_ctx.trace_id, "032x")
                span.set_attribute("correlation_id", correlation_id)

                logger.info("Sending TTS request to Deepgram.", extra={"provider": self.provider_name, "correlation_id": correlation_id})
                
                # Deepgram SDK v5 returns a synchronous Iterator[bytes]
                # We need to consume it in a non-blocking way
                def _consume_generator():
                    chunks = self.client.speak.v1.audio.generate(
                        text=text,
                        model="aura-asteria-en"
                    )
                    return b"".join(chunks)
                
                # Run the synchronous generator in a thread pool to avoid blocking
                response = await asyncio.to_thread(_consume_generator)
                
                logger.info("Received TTS response from Deepgram.", extra={"provider": self.provider_name, "correlation_id": correlation_id})
                # Response is already bytes in v5
                return response
                
            except Exception as e:
                status = "error"
                VOICE_ERRORS.labels(provider=self.provider_name, type="tts", error_type=type(e).__name__).inc()
                logger.error(f"Deepgram TTS failed: {e}", extra={"provider": self.provider_name, "error": str(e), "correlation_id": correlation_id})
                span.record_exception(e)
                raise
            finally:
                duration = time.time() - start_time
                VOICE_REQUESTS.labels(provider=self.provider_name, type="tts", status=status).inc()
                VOICE_LATENCY.labels(provider=self.provider_name, type="tts").observe(duration)

    async def health_check(self) -> bool:
        return True
