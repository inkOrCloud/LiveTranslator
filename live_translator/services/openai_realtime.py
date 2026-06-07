"""OpenAI Realtime API streaming ASR implementation."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class _RealtimeSession:
    """Internal implementation of ASRSession for OpenAI Realtime API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        on_partial: Callable[[str], None] | None = None,
        on_final: Callable[[str], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        """Initialize the session.

        Args:
            api_key: OpenAI API key.
            model: Model ID for the Realtime API.
            on_partial: Callback for partial transcription.
            on_final: Callback for final transcription.
            on_error: Callback for errors.
        """
        self._api_key = api_key
        self._model = model
        self._on_partial_cb = on_partial
        self._on_final_cb = on_final
        self._on_error_cb = on_error
        self._ws: Any = None
        self._connected = False

        logger.debug("RealtimeSession created: model=%s", model)

    def _connect(self) -> None:
        """Establish WebSocket connection to OpenAI Realtime API."""
        try:
            import websockets.sync.client as ws_client
        except ImportError:
            raise RuntimeError(
                "websockets library required for OpenAI Realtime API. "
                "Install with: uv add websockets"
            ) from None

        url = f"wss://api.openai.com/v1/realtime?model={self._model}"
        logger.info("Connecting to OpenAI Realtime API: model=%s", self._model)

        try:
            self._ws = ws_client.connect(
                url,
                additional_headers={
                    "Authorization": f"Bearer {self._api_key[:8]}...",
                    "OpenAI-Beta": "realtime=v1",
                },
            )
            self._connected = True
            logger.info("OpenAI Realtime WebSocket connected")

            # Send session update to enable audio transcription
            self._ws.send(
                json.dumps(
                    {
                        "type": "session.update",
                        "session": {
                            "modalities": ["text"],
                            "instructions": "",
                            "input_audio_transcription": {
                                "enabled": True,
                                "model": "whisper-1",
                            },
                        },
                    }
                )
            )
            logger.debug("Session update sent to OpenAI Realtime API")

        except Exception:
            logger.exception("Failed to connect to OpenAI Realtime API")
            self._connected = False
            raise

    def send_audio(self, chunk: bytes) -> None:
        """Send an audio chunk (PCM16, 16kHz, mono) for recognition.

        Args:
            chunk: Raw PCM16 audio data at 16kHz sample rate.
        """
        if not self._connected:
            self._connect()

        import base64

        audio_b64 = base64.b64encode(chunk).decode("ascii")
        try:
            self._ws.send(
                json.dumps(
                    {
                        "type": "input_audio_buffer.append",
                        "audio": audio_b64,
                    }
                )
            )
        except Exception as exc:
            logger.exception("Failed to send audio chunk")
            if self._on_error_cb:
                self._on_error_cb(exc)

    def on_partial(self, callback: Callable[[str], None]) -> None:
        """Register callback for partial transcription."""
        self._on_partial_cb = callback

    def on_final(self, callback: Callable[[str], None]) -> None:
        """Register callback for final transcription."""
        self._on_final_cb = callback

    def on_error(self, callback: Callable[[Exception], None]) -> None:
        """Register callback for errors."""
        self._on_error_cb = callback

    def _handle_messages(self) -> None:
        """Non-blocking read of incoming WebSocket messages."""
        if not self._ws:
            return
        try:
            message = self._ws.recv(timeout=0.001)
            data = json.loads(message)
            msg_type = data.get("type", "")

            if msg_type == "conversation.item.input_audio_transcription.completed":
                transcript = data.get("transcript", "")
                if transcript:
                    logger.debug("OpenAI ASR final transcript (%d chars): %s...",
                                 len(transcript), transcript[:60])
                if transcript and self._on_final_cb:
                    self._on_final_cb(transcript)

            elif msg_type == "conversation.item.input_audio_transcription.in_progress":
                transcript = data.get("transcript", "")
                if transcript and self._on_partial_cb:
                    logger.debug("OpenAI ASR partial transcript (%d chars)", len(transcript))
                    self._on_partial_cb(transcript)

            elif msg_type == "error":
                error_msg = data.get("error", {}).get("message", "Unknown error")
                logger.error("OpenAI Realtime API server error: %s", error_msg)
                if self._on_error_cb:
                    self._on_error_cb(RuntimeError(error_msg))

            elif msg_type in ("session.created", "session.updated"):
                logger.info("OpenAI Realtime session %s", msg_type)

            elif msg_type in (
                    "input_audio_buffer.speech_started",
                    "input_audio_buffer.speech_stopped",
                ):
                logger.debug("OpenAI speech boundary: %s", msg_type)

            elif msg_type == "response.done":
                logger.debug("OpenAI response done")

            else:
                logger.debug("OpenAI unhandled message type: %s", msg_type)

        except TimeoutError:
            pass
        except Exception as exc:
            logger.exception("OpenAI Realtime poll error")
            if self._on_error_cb:
                self._on_error_cb(exc)

    def poll(self) -> None:
        """Poll for incoming messages. Called periodically from pipeline."""
        self._handle_messages()

    def close(self) -> None:
        """Close the WebSocket connection."""
        self._connected = False
        if self._ws:
            logger.info("Closing OpenAI Realtime WebSocket connection")
            try:
                self._ws.close()
            except Exception:
                logger.debug("Ignored error closing WebSocket", exc_info=True)
            self._ws = None
        logger.debug("OpenAI Realtime session closed")

    @property
    def is_alive(self) -> bool:
        """Whether the session is connected."""
        return self._connected and self._ws is not None


class OpenAIRealtimeService:
    """SpeechRecognizer implementation using OpenAI Realtime API."""

    service_id = "openai_realtime"
    display_name = "OpenAI Realtime API"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the service.

        Args:
            config: Optional config dict with api_key and model.
        """
        self.config = config or {
            "api_key": "",
            "model": "gpt-4o-realtime-preview",
        }
        logger.debug("OpenAIRealtimeService initialized: model=%s",
                     self.config.get("model", "unknown"))

    def create_session(self) -> _RealtimeSession:
        """Create a new streaming recognition session.

        Returns:
            An ASRSession connected to OpenAI Realtime API.

        Raises:
            RuntimeError: If API key is not configured.
        """
        api_key = self.config.get("api_key", "")
        if not api_key:
            raise RuntimeError("OpenAI API key not configured")
        model = self.config.get("model", "gpt-4o-realtime-preview")
        logger.info("Creating OpenAI Realtime session: model=%s", model)
        return _RealtimeSession(
            api_key=api_key,
            model=model,
        )

    @classmethod
    def config_schema(cls) -> dict[str, Any]:
        """Return JSON Schema for OpenAI Realtime configuration.

        Returns:
            JSON Schema dict with api_key and model fields.
        """
        return {
            "type": "object",
            "title": "OpenAI Realtime API Configuration",
            "properties": {
                "api_key": {
                    "type": "string",
                    "title": "API Key",
                    "description": "Your OpenAI API key",
                    "format": "password",
                },
                "model": {
                    "type": "string",
                    "title": "Model",
                    "description": "Realtime model ID",
                    "default": "gpt-4o-realtime-preview",
                    "enum": [
                        "gpt-4o-realtime-preview",
                        "gpt-4o-mini-realtime-preview",
                    ],
                },
            },
            "required": ["api_key"],
        }
