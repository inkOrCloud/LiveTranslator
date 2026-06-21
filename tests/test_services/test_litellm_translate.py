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
    assert "enable_context" in service.config
    assert "max_context_tokens" in service.config
    assert service.config["model"] == "gpt-4o-mini"
    assert service.config["max_tokens"] == 1024
    assert service.config["temperature"] == 0.3
    assert service.config["enable_context"] is True
    assert service.config["max_context_tokens"] == 4000


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
    # The user message should contain the context block with the current text
    assert "Hello" in call_kwargs["messages"][1]["content"]


def test_translate_context_off_uses_raw_text() -> None:
    """With enable_context=False, translate() should behave as before."""
    service = LiteLLMTranslateService(
        {
            "model": "gpt-4o-mini",
            "api_key": "test-key",
            "enable_context": False,
        }
    )
    with patch("litellm.completion") as mock_completion:
        mock_completion.return_value.choices = [
            type("Choice", (), {"message": type("Msg", (), {"content": "你好"})})()
        ]
        service.translate("Hello", "auto", "Chinese")
    messages = mock_completion.call_args.kwargs["messages"]
    # With context off, the user message is just the raw text
    assert messages[1]["content"] == "Hello"


def test_translate_custom_prompt_context_on() -> None:
    """With custom system_prompt and context on, {text} receives the context block."""
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
    # The {text} placeholder is replaced with the context block (including current text)
    content = messages[0]["content"]
    assert content.startswith("Translate to Chinese: [当前待翻译文本 / Current Text to Translate]")
    assert "Hello" in content


def test_translate_custom_prompt_context_off() -> None:
    """With custom system_prompt and context off, {text} is just the raw text."""
    service = LiteLLMTranslateService(
        {
            "model": "gpt-4o-mini",
            "api_key": "test-key",
            "system_prompt": "Translate to {target_lang}: {text}",
            "enable_context": False,
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
    codes = [lang["code"] for lang in langs]
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
    assert "enable_context" in schema["properties"]
    assert "max_context_tokens" in schema["properties"]
    assert schema["properties"]["api_key"]["format"] == "password"
    assert schema["properties"]["enable_context"]["default"] is True
    assert schema["properties"]["max_context_tokens"]["default"] == 4000


# ── Context enhancement tests ──────────────────────────────────


def test_context_stores_translation_pair() -> None:
    """translate() should store the original and translation in context."""
    service = LiteLLMTranslateService(
        {"model": "gpt-4o-mini", "api_key": "test-key"}
    )
    assert service.translation_context.item_count == 0

    with patch("litellm.completion") as mock_completion:
        mock_completion.return_value.choices = [
            type("Choice", (), {"message": type("Msg", (), {"content": "你好"})})()
        ]
        service.translate("Hello", "auto", "Chinese")

    assert service.translation_context.item_count == 1
    item = service.translation_context.history[0]
    assert item.original == "Hello"
    assert item.translated == "你好"


def test_context_builds_up_over_multiple_calls() -> None:
    """translate() should accumulate history across calls."""
    service = LiteLLMTranslateService(
        {"model": "gpt-4o-mini", "api_key": "test-key"}
    )

    with patch("litellm.completion") as mock_completion:
        mock_completion.return_value.choices = [
            type("Choice", (), {"message": type("Msg", (), {"content": "你好"})})()
        ]
        service.translate("Hello", "auto", "Chinese")
        mock_completion.return_value.choices = [
            type("Choice", (), {"message": type("Msg", (), {"content": "你好吗"})})()
        ]
        service.translate("How are you", "auto", "Chinese")

    assert service.translation_context.item_count == 2
    assert service.translation_context.history[0].original == "Hello"
    assert service.translation_context.history[1].original == "How are you"


def test_context_block_includes_history() -> None:
    """After multiple translations, the context block should include history."""
    service = LiteLLMTranslateService(
        {"model": "gpt-4o-mini", "api_key": "test-key"}
    )

    with patch("litellm.completion") as mock_completion:
        mock_completion.return_value.choices = [
            type("Choice", (), {"message": type("Msg", (), {"content": "你好"})})()
        ]
        service.translate("Hello", "auto", "Chinese")
        mock_completion.return_value.choices = [
            type("Choice", (), {"message": type("Msg", (), {"content": "我很好"})})()
        ]
        service.translate("I'm fine", "auto", "Chinese")

    # Check that the last call's messages include history
    all_calls = mock_completion.call_args_list
    last_messages = all_calls[-1].kwargs["messages"]
    last_content = last_messages[1]["content"]
    assert "Hello" in last_content  # Previous original
    assert "你好" in last_content   # Previous translation
    assert "I'm fine" in last_content  # Current text


def test_reset_context() -> None:
    """reset_context() should clear background and history."""
    service = LiteLLMTranslateService(
        {"model": "gpt-4o-mini", "api_key": "test-key"}
    )

    with patch("litellm.completion") as mock_completion:
        mock_completion.return_value.choices = [
            type("Choice", (), {"message": type("Msg", (), {"content": "你好"})})()
        ]
        service.translate("Hello", "auto", "Chinese")

    assert service.translation_context.item_count == 1
    service.reset_context()
    assert service.translation_context.item_count == 0
    assert service.translation_context.background == ""


def test_context_disabled_does_not_store() -> None:
    """With enable_context=False, context should not store history."""
    service = LiteLLMTranslateService(
        {
            "model": "gpt-4o-mini",
            "api_key": "test-key",
            "enable_context": False,
        }
    )

    with patch("litellm.completion") as mock_completion:
        mock_completion.return_value.choices = [
            type("Choice", (), {"message": type("Msg", (), {"content": "你好"})})()
        ]
        service.translate("Hello", "auto", "Chinese")

    assert service.translation_context.item_count == 0


def test_translation_context_property() -> None:
    """translation_context should return the internal context instance."""
    service = LiteLLMTranslateService()
    ctx = service.translation_context
    assert ctx is service._context  # noqa: SLF001
