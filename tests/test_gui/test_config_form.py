"""Tests for config form widget."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from live_translator.gui.config_form import ConfigFormBuilder


def test_config_form_builds_widgets(qapp: QApplication) -> None:
    """ConfigFormBuilder should create widgets from JSON Schema."""
    schema = {
        "type": "object",
        "properties": {
            "api_key": {
                "type": "string",
                "title": "API Key",
                "format": "password",
            },
            "model": {
                "type": "string",
                "title": "Model",
                "default": "whisper-1",
                "enum": ["whisper-1", "whisper-large-v3"],
            },
            "enabled": {
                "type": "boolean",
                "title": "Enabled",
                "default": True,
            },
            "timeout": {
                "type": "number",
                "title": "Timeout",
                "default": 30.0,
            },
        },
        "required": ["api_key"],
    }

    builder = ConfigFormBuilder(schema, {"api_key": "sk-test", "model": "whisper-1"})
    builder.build()

    assert builder.get_widget("api_key") is not None
    assert builder.get_widget("model") is not None
    assert builder.get_widget("enabled") is not None
    assert builder.get_widget("timeout") is not None


def test_config_form_get_values(qapp: QApplication) -> None:
    """get_values should return current widget values."""
    schema = {
        "type": "object",
        "properties": {
            "api_key": {
                "type": "string",
                "title": "API Key",
                "format": "password",
            },
            "model": {
                "type": "string",
                "title": "Model",
                "default": "whisper-1",
                "enum": ["whisper-1"],
            },
        },
        "required": ["api_key"],
    }

    builder = ConfigFormBuilder(schema, {"api_key": "test-key", "model": "whisper-1"})
    builder.build()

    values = builder.get_values()
    assert values["api_key"] == "test-key"
    assert values["model"] == "whisper-1"
