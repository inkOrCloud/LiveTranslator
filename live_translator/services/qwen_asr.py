"""Qwen-ASR-Realtime streaming ASR implementation via WebSocket direct connection."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from typing import Any

from websockets.exceptions import ConnectionClosedError

logger = logging.getLogger(__name__)

# 匹配中英文句尾标点，用于句子级 final 检测
_SENTENCE_END_RE = re.compile(r"(?<=[。！？.!?\n])")


class _QwenASRSession:
    """Internal implementation of ASRSession for Qwen ASR Realtime API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        session_config: dict[str, Any] | None = None,
        on_partial: Callable[[str], None] | None = None,
        on_final: Callable[[str], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        """Initialize the session.

        Args:
            api_key: Alibaba Cloud DashScope API key.
            model: Model ID (e.g. ``qwen3-asr-flash-realtime``).
            session_config: Optional dict with language and VAD parameters.
            on_partial: Callback for partial transcription.
            on_final: Callback for final transcription.
            on_error: Callback for errors.
        """
        self._api_key = api_key
        self._model = model
        self._session_config = dict(session_config or {})
        self._on_partial_cb = on_partial
        self._on_final_cb = on_final
        self._on_error_cb = on_error
        self._ws: Any = None
        self._connected = False
        self._emitted_text: str = ""

    def _connect(self) -> None:
        """Establish WebSocket connection to Qwen ASR Realtime API."""
        try:
            import websockets.sync.client as ws_client
        except ImportError:
            raise RuntimeError(
                "websockets library required for Qwen ASR Realtime. "
                "Install with: uv add websockets"
            ) from None

        url = f"wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model={self._model}"
        self._ws = ws_client.connect(
            url,
            additional_headers={
                "Authorization": f"Bearer {self._api_key}",
            },
        )
        self._connected = True

        # Build session.update payload
        session_payload: dict[str, Any] = {
            "type": "session.update",
            "session": {
                "input_audio_format": "pcm",
                "sample_rate": 16000,
                "input_audio_transcription": {
                    "language": self._session_config.get("language", "zh"),
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": self._session_config.get("vad_threshold", 0.0),
                    "silence_duration_ms": self._session_config.get(
                        "vad_silence_duration_ms", 400
                    ),
                },
            },
        }

        self._ws.send(json.dumps(session_payload))

    def send_audio(self, chunk: bytes) -> None:
        """Send an audio chunk (PCM16, 16kHz, mono) for recognition.

        Args:
            chunk: Raw PCM16 audio data.
        """
        if not self._connected:
            self._connect()

        if not self._connected:
            return

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
        except ConnectionClosedError:
            self._connected = False

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
        if not self._ws or not self._connected:
            return
        try:
            message = self._ws.recv(timeout=0.001)
            data = json.loads(message)
            msg_type = data.get("type", "")

            if msg_type == "conversation.item.input_audio_transcription.completed":
                transcript = data.get("transcript", "")
                if transcript and self._on_final_cb:
                    self._on_final_cb(transcript)

            elif msg_type == "conversation.item.input_audio_transcription.text":
                text = data.get("text", "")
                stash = data.get("stash", "")
                combined = f"{text}{stash}"
                if combined and self._on_partial_cb:
                    self._on_partial_cb(combined)

            elif msg_type == "error":
                error_msg = data.get("error", {}).get("message", "Unknown error")
                logger.error("Qwen ASR server error: %s", error_msg)
                if self._on_error_cb:
                    self._on_error_cb(RuntimeError(error_msg))

            elif msg_type in ("session.created", "session.updated"):
                logger.info(
                "Qwen ASR session %s: %s", msg_type,
                data.get("session", {}).get("id", ""),
            )

            elif msg_type in (
                    "input_audio_buffer.speech_started",
                    "input_audio_buffer.speech_stopped",
                ):
                logger.debug("Qwen ASR speech boundary: %s", msg_type)

            elif msg_type == "session.finished":
                self._connected = False
                logger.info("Qwen ASR session finished")

        except TimeoutError:
            pass
        except ConnectionClosedError:
            logger.warning("Qwen ASR connection closed")
            self._connected = False
            self._ws = None
        except Exception as exc:
            logger.exception("Qwen ASR poll error")
            if self._on_error_cb:
                self._on_error_cb(exc)

    def poll(self) -> None:
        """Poll for incoming messages. Called periodically from pipeline."""
        if not self._connected:
            return
        self._handle_messages()

    def close(self) -> None:
        """Close the WebSocket connection."""
        self._connected = False
        if self._ws:
            try:
                self._ws.send(
                    json.dumps({"type": "session.finish", "event_id": "session_finish_001"})
                )
            except Exception:
                pass
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

    @property
    def is_alive(self) -> bool:
        """Whether the session is connected."""
        return self._connected and self._ws is not None


class QwenASRService:
    """SpeechRecognizer implementation using Qwen ASR Realtime API."""

    service_id = "qwen_asr"
    display_name = "Qwen ASR Realtime"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the service.

        Args:
            config: Optional config dict with api_key, model, language, etc.
        """
        self.config = config or {
            "api_key": "",
            "model": "qwen3-asr-flash-realtime",
            "language": "zh",
        }

    def create_session(self) -> _QwenASRSession:
        """Create a new streaming recognition session.

        Returns:
            An ASRSession connected to Qwen ASR Realtime API.

        Raises:
            RuntimeError: If API key is not configured.
        """
        api_key = self.config.get("api_key", "")
        if not api_key:
            raise RuntimeError("Qwen API key not configured")
        model = self.config.get("model", "qwen3-asr-flash-realtime")
        session_config = {
            "language": self.config.get("language", "zh"),
            "vad_threshold": self.config.get("vad_threshold", 0.0),
            "vad_silence_duration_ms": self.config.get("vad_silence_duration_ms", 400),
        }
        return _QwenASRSession(
            api_key=api_key,
            model=model,
            session_config=session_config,
        )

    @classmethod
    def config_schema(cls) -> dict[str, Any]:
        """Return JSON Schema for Qwen ASR Realtime configuration.

        Returns:
            JSON Schema dict with api_key, model, language.
        """
        return {
            "type": "object",
            "title": "Qwen ASR Realtime Configuration",
            "properties": {
                "api_key": {
                    "type": "string",
                    "title": "API Key",
                    "description": "Your Alibaba Cloud DashScope API key",
                    "format": "password",
                },
                "model": {
                    "type": "string",
                    "title": "Model",
                    "description": "ASR model ID",
                    "default": "qwen3-asr-flash-realtime",
                    "enum": ["qwen3-asr-flash-realtime"],
                },
                "language": {
                    "type": "string",
                    "title": "Language",
                    "description": "Audio language code",
                    "default": "zh",
                    "enum": [
                        "zh", "yue", "en", "ja", "de", "ko", "ru", "fr", "pt",
                        "ar", "it", "es", "hi", "id", "th", "tr", "uk", "vi",
                    ],
                },
            },
            "required": ["api_key"],
        }
