"""Tests for DeepL translator service."""

from __future__ import annotations

from live_translator.services.deepl_translate import DeepLTranslateService


def test_deepl_config_schema() -> None:
    """config_schema should return valid JSON Schema."""
    schema = DeepLTranslateService.config_schema()
    assert schema["type"] == "object"
    assert "api_key" in schema["properties"]
    assert schema["properties"]["api_key"]["format"] == "password"


def test_deepl_default_config() -> None:
    """Default config should include api_key and target_lang."""
    service = DeepLTranslateService()
    assert "api_key" in service.config
    assert service.config["target_lang"] == "ZH"


def test_deepl_service_identity() -> None:
    """Service should expose correct identity attributes."""
    service = DeepLTranslateService()
    assert service.service_id == "deepl"
    assert service.display_name == "DeepL API"
