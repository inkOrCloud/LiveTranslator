"""Tests for main control panel window."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtWidgets import QApplication

from live_translator.gui.main_window import MainWindow
from live_translator.config.manager import ConfigManager


def _make_config() -> ConfigManager:
    """Create a temporary config for tests."""
    tmp = tempfile.mkdtemp()
    return ConfigManager(Path(tmp) / "config.json")


def test_main_window_creation(qapp: QApplication) -> None:
    """MainWindow should create without error."""
    window = MainWindow(_make_config())
    assert window.windowTitle() == "LiveTranslator"
