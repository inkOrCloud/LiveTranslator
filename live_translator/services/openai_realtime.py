"""OpenAI Realtime API streaming ASR implementation."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any


class _RealtimeSession:
    """Internal implementation of ASRSession for OpenAI Realtime API."""

    def __init__(self, api_key: str, model: str,
                 on_partial: Callable[[str], None] | None = None,
                 on_final: Callable[[str], None] | None = None,
                 on_error: Callable[[Exception], None] | None = None) -> None:
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
        self._ws = ws_client.connect(
            url,
            additional_headers={
                "Authorization": f"Bearer {self._api_key}",
                "OpenAI-Beta": "realtime=v1",
            },
        )
        self._connected = True

        # Send session update to enable audio transcription
        self._ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "modalities": ["text"],
                "instructions": "",
                "input_audio_transcription": {
                    "enabled": True,
                    "model": "whisper-1",
                },
            },
        }))

    def send_audio(self, chunk: bytes) -> None:
        """Send an audio chunk (PCM16, 16kHz, mono) for recognition.

        Args:
            chunk: Raw PCM16 audio data at 16kHz sample rate.
        """
        if not self._connected:
            self._connect()

        import base64
        audio_b64 = base64.b64encode(chunk).decode("ascii")
        self._ws.send(json.dumps({
            "type": "input_audio_buffer.append",
            "audio": audio_b64,
        }))

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
                if transcript and self._on_final_cb:
                    self._on_final_cb(transcript)

            elif msg_type == "conversation.item.input_audio_transcription.in_progress":
                transcript = data.get("transcript", "")
                if transcript and self._on_partial_cb:
                    self._on_partial_cb(transcript)

            elif msg_type == "error":
                error_msg = data.get("error", {}).get("message", "Unknown error")
                if self._on_error_cb:
                    self._on_error_cb(RuntimeError(error_msg))

        except (TimeoutError, TimeoutError):
            pass
        except Exception as exc:
            if self._on_error_cb:
                self._on_error_cb(exc)

    def poll(self) -> None:
        """Poll for incoming messages. Called periodically from pipeline."""
        self._handle_messages()

    def close(self) -> None:
        """Close the WebSocket connection."""
        self._connected = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

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
