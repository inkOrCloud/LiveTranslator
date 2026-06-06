"""Tests for OpenAI Realtime ASR service."""

from __future__ import annotations

from live_translator.services.openai_realtime import OpenAIRealtimeService


def test_realtime_config_schema() -> None:
    """config_schema should return valid JSON Schema."""
    schema = OpenAIRealtimeService.config_schema()
    assert schema["type"] == "object"
    assert "api_key" in schema["properties"]
    assert schema["properties"]["model"]["default"] == "gpt-4o-realtime-preview"


def test_realtime_service_identity() -> None:
    """Service should expose correct identity attributes."""
    service = OpenAIRealtimeService()
    assert service.service_id == "openai_realtime"
    assert service.display_name == "OpenAI Realtime API"
    assert service.config["model"] == "gpt-4o-realtime-preview"


def test_realtime_create_session_no_key() -> None:
    """create_session without API key should raise RuntimeError."""
    service = OpenAIRealtimeService({"api_key": "", "model": "gpt-4o-realtime-preview"})
    import pytest
    with pytest.raises(RuntimeError, match="OpenAI API key not configured"):
        service.create_session()
