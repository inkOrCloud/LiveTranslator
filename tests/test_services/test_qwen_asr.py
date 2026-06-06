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
