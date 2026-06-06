"""Tests for LiteLLM translator service."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from live_translator.services.litellm_translate import LiteLLMTranslateService


def test_service_identity() -> None:
    """Service should expose correct identity attributes."""
    service = LiteLLMTranslateService()
    assert service.service_id == "litellm"
    assert service.display_name == "LiteLLM (多模型)"


def test_default_config() -> None:
    """Default config should include expected fields."""
    service = LiteLLMTranslateService()
    assert "model" in service.config
    assert "api_key" in service.config
    assert "api_base" in service.config
    assert "max_tokens" in service.config
    assert "temperature" in service.config
    assert "system_prompt" in service.config
    assert service.config["model"] == "gpt-4o-mini"
    assert service.config["max_tokens"] == 1024
    assert service.config["temperature"] == 0.3


def test_translate_raises_without_model() -> None:
    """translate() should raise RuntimeError when model is empty."""
    service = LiteLLMTranslateService({"model": "", "api_key": "test"})
    with pytest.raises(RuntimeError, match="LiteLLM model not configured"):
        service.translate("Hello", "auto", "Chinese")


def test_translate_success() -> None:
    """translate() should call litellm.completion and return translated text."""
    service = LiteLLMTranslateService(
        {"model": "gpt-4o-mini", "api_key": "test-key"}
    )
    with patch("litellm.completion") as mock_completion:
        mock_completion.return_value.choices = [
            type("Choice", (), {"message": type("Msg", (), {"content": "你好"})})()
        ]
        result = service.translate("Hello", "auto", "Chinese")
    assert result == "你好"
    mock_completion.assert_called_once()
    call_kwargs = mock_completion.call_args.kwargs
    assert call_kwargs["model"] == "gpt-4o-mini"
    assert "Hello" in call_kwargs["messages"][1]["content"]


def test_translate_custom_prompt() -> None:
    """translate() should use custom system_prompt if provided."""
    service = LiteLLMTranslateService(
        {
            "model": "gpt-4o-mini",
            "api_key": "test-key",
            "system_prompt": "Translate to {target_lang}: {text}",
        }
    )
    with patch("litellm.completion") as mock_completion:
        mock_completion.return_value.choices = [
            type("Choice", (), {"message": type("Msg", (), {"content": "你好"})})()
        ]
        service.translate("Hello", "auto", "Chinese")
    messages = mock_completion.call_args.kwargs["messages"]
    assert messages[0]["content"] == "Translate to Chinese: Hello"


def test_translate_passes_optional_params() -> None:
    """translate() should pass api_base, max_tokens, temperature to litellm."""
    service = LiteLLMTranslateService(
        {
            "model": "gpt-4o-mini",
            "api_key": "test-key",
            "api_base": "https://custom.endpoint",
            "max_tokens": 512,
            "temperature": 0.7,
        }
    )
    with patch("litellm.completion") as mock_completion:
        mock_completion.return_value.choices = [
            type("Choice", (), {"message": type("Msg", (), {"content": "你好"})})()
        ]
        service.translate("Hello", "auto", "Chinese")
    kwargs = mock_completion.call_args.kwargs
    assert kwargs.get("api_base") == "https://custom.endpoint"
    assert kwargs.get("max_tokens") == 512
    assert kwargs.get("temperature") == 0.7


def test_translate_partial_returns_none() -> None:
    """translate_partial() should return None (sync mode)."""
    service = LiteLLMTranslateService()
    result = service.translate_partial("Hello", "auto", "Chinese")
    assert result is None


def test_supported_languages() -> None:
    """supported_languages() should return list of dicts with code/name."""
    service = LiteLLMTranslateService()
    langs = service.supported_languages()
    assert isinstance(langs, list)
    assert len(langs) > 3
    for lang in langs:
        assert "code" in lang
        assert "name" in lang
    codes = [l["code"] for l in langs]
    assert "ZH" in codes
    assert "EN" in codes
    assert "custom" in codes


def test_config_schema() -> None:
    """config_schema() should return valid JSON Schema."""
    schema = LiteLLMTranslateService.config_schema()
    assert schema["type"] == "object"
    assert "model" in schema["properties"]
    assert "api_key" in schema["properties"]
    assert "api_base" in schema["properties"]
    assert "max_tokens" in schema["properties"]
    assert "temperature" in schema["properties"]
    assert "system_prompt" in schema["properties"]
    assert schema["properties"]["api_key"]["format"] == "password"
