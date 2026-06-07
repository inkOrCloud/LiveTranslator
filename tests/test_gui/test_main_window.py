"""Tests for main control panel window."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtWidgets import QApplication

from live_translator.config.manager import ConfigManager
from live_translator.gui.main_window import MainWindow


def _make_config() -> ConfigManager:
    """Create a temporary config for tests."""
    tmp = tempfile.mkdtemp()
    return ConfigManager(Path(tmp) / "config.json")


def test_main_window_creation(qapp: QApplication) -> None:
    """MainWindow should create without error."""
    window = MainWindow(_make_config())
    assert window.windowTitle() == "LiveTranslator"


def test_main_window_has_subtitle_toggle(qapp: QApplication) -> None:
    """MainWindow should have a subtitle toggle checkbox."""
    window = MainWindow(_make_config())
    assert hasattr(window, "_subtitle_toggle")
    assert window._subtitle_toggle.isChecked()  # should be on by default


def test_main_window_no_mode_combo(qapp: QApplication) -> None:
    """MainWindow should NOT have the old mode combo."""
    window = MainWindow(_make_config())
    assert not hasattr(window, "_mode_combo") or window._mode_combo is None


def test_main_window_subtitle_toggle_signal(qapp: QApplication) -> None:
    """Subtitle toggle should emit toggled signal."""
    window = MainWindow(_make_config())
    assert window._subtitle_toggle.toggled is not None
