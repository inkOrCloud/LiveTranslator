# Qwen-ASR-Realtime Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a streaming ASR service using Alibaba Cloud Qwen-ASR-Realtime API via WebSocket direct connection.

**Architecture:** Following the exact same pattern as `OpenAIRealtimeService` — a `_QwenASRSession` class implementing the `ASRSession` protocol (lazy WS connect, `send_audio`, `poll`, `close`), and a `QwenASRService` class implementing the `SpeechRecognizer` protocol with `config_schema()` and `create_session()`.

**Tech Stack:** Python 3.12, websockets (existing), dashscope (not used — direct WS), pytest, ruff, mypy

---

### Task 1: Write failing tests for QwenASRService identity and config schema

**Files:**
- Create: `tests/test_services/test_qwen_asr.py`

- [ ] **Step 1: Create test file with identity and schema tests**

```python
"""Tests for Qwen ASR Realtime service."""

from __future__ import annotations

import pytest

from live_translator.services.qwen_asr import QwenASRService


def test_qwen_asr_config_schema() -> None:
    """config_schema should return valid JSON Schema with expected fields."""
    schema = QwenASRService.config_schema()
    assert schema["type"] == "object"
    assert "api_key" in schema["properties"]
    assert schema["properties"]["api_key"]["format"] == "password"
    assert schema["properties"]["model"]["default"] == "qwen3-asr-flash-realtime"
    assert schema["properties"]["language"]["default"] == "zh"
    assert schema["properties"]["sample_rate"]["default"] == 16000
    assert schema["properties"]["input_audio_format"]["default"] == "pcm"
    assert "api_key" in schema["required"]


def test_qwen_asr_service_identity() -> None:
    """Service should expose correct identity attributes."""
    service = QwenASRService()
    assert service.service_id == "qwen_asr"
    assert service.display_name == "Qwen ASR Realtime"
    assert service.config["model"] == "qwen3-asr-flash-realtime"
    assert service.config["api_key"] == ""


def test_qwen_asr_create_session_no_key() -> None:
    """create_session without API key should raise RuntimeError."""
    service = QwenASRService({"api_key": "", "model": "qwen3-asr-flash-realtime"})
    with pytest.raises(RuntimeError, match="Qwen API key not configured"):
        service.create_session()


def test_qwen_asr_create_session_with_config() -> None:
    """create_session should pass session_config to the session."""
    service = QwenASRService({
        "api_key": "test-key-123",
        "model": "qwen3-asr-flash-realtime",
        "language": "en",
        "sample_rate": 8000,
        "input_audio_format": "opus",
    })
    session = service.create_session()
    assert session._api_key == "test-key-123"
    assert session._model == "qwen3-asr-flash-realtime"
    assert session._session_config["language"] == "en"
    assert session._session_config["sample_rate"] == 8000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_services/test_qwen_asr.py -v 2>&1`
Expected: ModuleNotFoundError or ImportError — `qwen_asr` module doesn't exist yet

---

### Task 2: Implement QwenASRService and _QwenASRSession

**Files:**
- Create: `live_translator/services/qwen_asr.py`

- [ ] **Step 1: Create the full service module**

```python
"""Qwen-ASR-Realtime streaming ASR implementation via WebSocket direct connection."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


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
            session_config: Optional dict with language, sample_rate,
                input_audio_format, and VAD parameters.
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
                "input_audio_format": self._session_config.get("input_audio_format", "pcm"),
                "sample_rate": self._session_config.get("sample_rate", 16000),
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

        import base64

        audio_b64 = base64.b64encode(chunk).decode("ascii")
        self._ws.send(
            json.dumps(
                {
                    "type": "input_audio_buffer.append",
                    "audio": audio_b64,
                }
            )
        )

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

            elif msg_type == "conversation.item.input_audio_transcription.text":
                text = data.get("text", "")
                stash = data.get("stash", "")
                combined = f"{text}{stash}"
                if combined and self._on_partial_cb:
                    self._on_partial_cb(combined)

            elif msg_type == "error":
                error_msg = data.get("error", {}).get("message", "Unknown error")
                if self._on_error_cb:
                    self._on_error_cb(RuntimeError(error_msg))

            elif msg_type in ("session.created", "session.updated"):
                logger.info("Qwen ASR session %s: %s", msg_type, data.get("session", {}).get("id", ""))

            elif msg_type in ("input_audio_buffer.speech_started", "input_audio_buffer.speech_stopped"):
                logger.debug("Qwen ASR speech boundary: %s", msg_type)

            elif msg_type == "session.finished":
                logger.info("Qwen ASR session finished")

        except TimeoutError:
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
                import json as _json

                self._ws.send(
                    _json.dumps({"type": "session.finish", "event_id": "session_finish_001"})
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
            "sample_rate": 16000,
            "input_audio_format": "pcm",
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
            "sample_rate": self.config.get("sample_rate", 16000),
            "input_audio_format": self.config.get("input_audio_format", "pcm"),
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
            JSON Schema dict with api_key, model, language, sample_rate, format.
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
                "sample_rate": {
                    "type": "integer",
                    "title": "Sample Rate",
                    "default": 16000,
                    "enum": [8000, 16000],
                },
                "input_audio_format": {
                    "type": "string",
                    "title": "Audio Format",
                    "default": "pcm",
                    "enum": ["pcm", "opus"],
                },
            },
            "required": ["api_key"],
        }
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_services/test_qwen_asr.py -v 2>&1`
Expected: 4 passed

- [ ] **Step 3: Run ruff lint check**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run ruff check live_translator/services/qwen_asr.py tests/test_services/test_qwen_asr.py 2>&1`
Expected: No lint errors (or fix any reported)

- [ ] **Step 4: Run mypy type check**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run mypy live_translator/services/qwen_asr.py tests/test_services/test_qwen_asr.py 2>&1`
Expected: Success, no issues found

- [ ] **Step 5: Commit**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && git add live_translator/services/qwen_asr.py tests/test_services/test_qwen_asr.py && git commit -m "feat: add Qwen ASR Realtime streaming ASR service" 2>&1`

---

### Task 3: Write failing tests for _QwenASRSession event dispatch (mock WebSocket)

**Files:**
- Modify: `tests/test_services/test_qwen_asr.py`

- [ ] **Step 1: Add session event dispatch tests**

Append the following tests to `tests/test_services/test_qwen_asr.py`:

```python
from unittest.mock import MagicMock, patch


def test_qwen_asr_session_partial_text() -> None:
    """poll() should dispatch conversation.item.input_audio_transcription.text to on_partial."""
    service = QwenASRService({
        "api_key": "test-key",
        "model": "qwen3-asr-flash-realtime",
    })
    session = service.create_session()
    partial_results: list[str] = []
    session.on_partial(partial_results.append)

    mock_ws = MagicMock()
    mock_ws.recv.return_value = json.dumps({
        "type": "conversation.item.input_audio_transcription.text",
        "text": "你好",
        "stash": "世界",
    })
    session._ws = mock_ws
    session._connected = True

    session.poll()

    assert partial_results == ["你好世界"]


def test_qwen_asr_session_final_text() -> None:
    """poll() should dispatch completed event to on_final."""
    service = QwenASRService({
        "api_key": "test-key",
        "model": "qwen3-asr-flash-realtime",
    })
    session = service.create_session()
    final_results: list[str] = []
    session.on_final(final_results.append)

    mock_ws = MagicMock()
    mock_ws.recv.return_value = json.dumps({
        "type": "conversation.item.input_audio_transcription.completed",
        "transcript": "你好世界",
    })
    session._ws = mock_ws
    session._connected = True

    session.poll()

    assert final_results == ["你好世界"]


def test_qwen_asr_session_error_event() -> None:
    """poll() should dispatch error events to on_error."""
    service = QwenASRService({
        "api_key": "test-key",
        "model": "qwen3-asr-flash-realtime",
    })
    session = service.create_session()
    errors: list[Exception] = []
    session.on_error(errors.append)

    mock_ws = MagicMock()
    mock_ws.recv.return_value = json.dumps({
        "type": "error",
        "error": {"message": "Audio data too large"},
    })
    session._ws = mock_ws
    session._connected = True

    session.poll()

    assert len(errors) == 1
    assert "Audio data too large" in str(errors[0])


def test_qwen_asr_session_close_sends_finish() -> None:
    """close() should send session.finish and close the WebSocket."""
    service = QwenASRService({
        "api_key": "test-key",
        "model": "qwen3-asr-flash-realtime",
    })
    session = service.create_session()

    mock_ws = MagicMock()
    session._ws = mock_ws
    session._connected = True

    session.close()

    # Should send session.finish
    sent_calls = mock_ws.send.call_args_list
    finish_call = any(
        '"type": "session.finish"' in call[0][0]
        for call in sent_calls
    )
    assert finish_call, "Expected session.finish to be sent"
    mock_ws.close.assert_called_once()
    assert session.is_alive is False


def test_qwen_asr_session_is_alive() -> None:
    """is_alive should reflect connection state."""
    service = QwenASRService({
        "api_key": "test-key",
        "model": "qwen3-asr-flash-realtime",
    })
    session = service.create_session()
    assert session.is_alive is False

    mock_ws = MagicMock()
    session._ws = mock_ws
    session._connected = True
    assert session.is_alive is True

    session.close()
    assert session.is_alive is False


def test_qwen_asr_session_send_audio_lazy_connect() -> None:
    """send_audio should auto-connect if not already connected."""
    service = QwenASRService({
        "api_key": "test-key",
        "model": "qwen3-asr-flash-realtime",
    })
    session = service.create_session()

    with patch("websockets.sync.client.connect") as mock_connect:
        mock_ws = MagicMock()
        mock_connect.return_value = mock_ws

        session.send_audio(b"\x00\x01\x02\x03")

        mock_connect.assert_called_once()
        assert session._connected is True
        # Should have sent session.update + audio append
        assert mock_ws.send.call_count >= 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_services/test_qwen_asr.py -v 2>&1`
Expected: The existing 4 pass, but new tests may fail if session doesn't support mock injection (the `_ws` attribute on `_QwenASRSession` is `_ws`, so the existing code should already support mock injection). Let's see.

---

### Task 4: Implement event dispatch and verify tests pass

**Files:**
- Modify: `live_translator/services/qwen_asr.py` (already implemented in Task 2)

- [ ] **Step 1: Run tests to verify all pass**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_services/test_qwen_asr.py -v 2>&1`
Expected: All 10 tests pass

- [ ] **Step 2: Run ruff + mypy**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run ruff check live_translator/services/qwen_asr.py tests/test_services/test_qwen_asr.py 2>&1 && UV_CACHE_DIR=/tmp/uv-cache uv run mypy live_translator/services/qwen_asr.py tests/test_services/test_qwen_asr.py 2>&1`
Expected: No errors

- [ ] **Step 3: Run full test suite to check for regressions**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest -v 2>&1`
Expected: All tests pass (existing + new)

- [ ] **Step 4: Commit**

```bash
cd /home/ink/Desktop/develop/LiveTranslator && git add tests/test_services/test_qwen_asr.py && git commit -m "test: add Qwen ASR session event dispatch tests"
```

---

### Task 5: Register QwenASRService in app wiring

**Files:**
- Modify: `live_translator/gui/app.py`

- [ ] **Step 1: Add QwenASRService import and registration**

In `live_translator/gui/app.py`, in the `register_default_services()` method, add the import and registration:

```python
# Inside register_default_services(), add after openai_realtime registration:
from live_translator.services.qwen_asr import QwenASRService

qwen_asr_config = self._config.get_service_config(
    "asr",
    "qwen_asr",
)
self._registry.register(
    "asr",
    QwenASRService(qwen_asr_config),
)
```

And add `"live_translator/services/qwen_asr.py"` to the ruff per-file-ignores for `app.py` if needed (similar to openai_realtime line).

- [ ] **Step 2: Add ruff lint override for app.py for qwen_asr (if needed)**

In `pyproject.toml`, add `"live_translator/services/qwen_asr.py"` to the `[tool.ruff.lint.per-file-ignores]"live_translator/gui/app.py"` list? No — app.py already has `PLC0415` (lazy import) allowed. Actually, looking at the existing code, `PLC0415` is already in the app.py ignores list, so lazy imports are fine. Let me check if the register_default_services method already imports lazily — yes it does. So just adding the import inside the method is fine.

- [ ] **Step 3: Run tests to verify**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest -v 2>&1`
Expected: All tests pass

- [ ] **Step 4: Run ruff check**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run ruff check live_translator/gui/app.py 2>&1`
Expected: No new lint errors

- [ ] **Step 5: Commit**

```bash
cd /home/ink/Desktop/develop/LiveTranslator && git add live_translator/gui/app.py && git commit -m "feat: register Qwen ASR Realtime service in app wiring"
```
