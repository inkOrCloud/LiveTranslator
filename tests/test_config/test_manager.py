"""Tests for config manager."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from live_translator.config.manager import ConfigManager


def test_config_manager_defaults() -> None:
    """ConfigManager should provide sensible defaults."""
    config = ConfigManager(Path("/nonexistent/config.json"))
    assert config.get("audio.sample_rate") == 16000
    assert config.get("services.asr.active") == "openai_realtime"
    assert config.get("appearance.subtitle_size") == 28
    assert config.get("appearance.opacity") == 0.9


def test_config_manager_load_and_save() -> None:
    """ConfigManager should round-trip through JSON."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.json"
        config = ConfigManager(path)
        config.set("services.asr.active", "test_service")
        config.save()

        loaded = ConfigManager(path)
        assert loaded.get("services.asr.active") == "test_service"


def test_config_manager_dot_notation() -> None:
    """Nested keys should be accessible via dot notation."""
    config = ConfigManager(Path("/nonexistent/config.json"))
    config.set("a.b.c", 42)
    assert config._data["a"]["b"]["c"] == 42


def test_config_manager_get_with_default() -> None:
    """get() should return default for missing keys."""
    config = ConfigManager(Path("/nonexistent/config.json"))
    assert config.get("nonexistent.key", "fallback") == "fallback"
