"""Tests for Qwen ASR Realtime service."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

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
    })
    session = service.create_session()
    assert session._api_key == "test-key-123"
    assert session._model == "qwen3-asr-flash-realtime"
    assert session._session_config["language"] == "en"


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


def test_qwen_asr_config_schema_has_vad_silence_duration() -> None:
    """config_schema should include vad_silence_duration_ms for VAD segmentation."""
    schema = QwenASRService.config_schema()
    props = schema["properties"]

    assert "vad_silence_duration_ms" in props
    field = props["vad_silence_duration_ms"]
    assert field["type"] == "integer"
    assert field["default"] == 400
    assert field["minimum"] == 200
    assert field["maximum"] == 6000
    assert "VAD" in field.get("description", "")


def test_qwen_asr_create_session_passes_vad_silence_duration() -> None:
    """create_session should pass vad_silence_duration_ms to session_config."""
    service = QwenASRService({
        "api_key": "test-key",
        "model": "qwen3-asr-flash-realtime",
        "language": "zh",
        "vad_silence_duration_ms": 1200,
    })
    session = service.create_session()
    assert session._session_config["vad_silence_duration_ms"] == 1200


def test_qwen_asr_session_update_contains_vad_silence_duration() -> None:
    """_connect should send silence_duration_ms in session.update payload."""
    service = QwenASRService({
        "api_key": "test-key",
        "model": "qwen3-asr-flash-realtime",
        "language": "zh",
        "vad_silence_duration_ms": 600,
    })
    session = service.create_session()

    with patch("websockets.sync.client.connect") as mock_connect:
        mock_ws = MagicMock()
        mock_connect.return_value = mock_ws

        session.send_audio(b"\x00\x01\x02\x03")

        # Find the session.update message
        sent_calls = mock_ws.send.call_args_list
        update_payload = None
        for call in sent_calls:
            payload = json.loads(call[0][0])
            if payload.get("type") == "session.update":
                update_payload = payload
                break

        assert update_payload is not None, "session.update was not sent"
        turn_detection = update_payload["session"]["turn_detection"]
        assert turn_detection["silence_duration_ms"] == 600
        assert turn_detection["type"] == "server_vad"
