"""Tests for main control panel window."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from live_translator.gui.main_window import MainWindow
from live_translator.config.manager import ConfigManager


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """Create QApplication for widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def config() -> ConfigManager:
    """Create a temporary config for tests."""
    tmp = tempfile.mkdtemp()
    return ConfigManager(Path(tmp) / "config.json")


def test_main_window_creation(qapp: QApplication, config: ConfigManager) -> None:
    """MainWindow should create without error."""
    window = MainWindow(config)
    assert window.windowTitle() == "LiveTranslator"
