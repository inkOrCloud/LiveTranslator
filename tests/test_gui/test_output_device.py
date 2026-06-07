"""Tests for output device selection in MainWindow."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from live_translator.config.manager import ConfigManager
from live_translator.gui.main_window import MainWindow


@pytest.fixture
def config() -> ConfigManager:
    """Create a temporary config for tests."""
    tmp = tempfile.mkdtemp()
    return ConfigManager(Path(tmp) / "config.json")


@pytest.fixture
def window(config: ConfigManager, qapp: QApplication) -> MainWindow:
    """Create a MainWindow instance for testing."""
    return MainWindow(config)


# ---------------------------------------------------------------------------
#  UI element presence
# ---------------------------------------------------------------------------

class TestOutputDeviceUI:
    """The output device selector UI elements exist."""

    def test_has_output_sink_combo(self, window: MainWindow) -> None:
        assert hasattr(window, "_output_sink_combo")

    def test_has_refresh_button(self, window: MainWindow) -> None:
        assert hasattr(window, "_btn_refresh_sinks")

    def test_has_populate_method(self, window: MainWindow) -> None:
        assert hasattr(window, "populate_sink_selector")
        assert callable(window.populate_sink_selector)

    def test_has_get_output_sink_method(self, window: MainWindow) -> None:
        assert hasattr(window, "get_output_sink")
        assert callable(window.get_output_sink)


# ---------------------------------------------------------------------------
#  populate_sink_selector
# ---------------------------------------------------------------------------

class TestPopulateSinkSelector:
    """MainWindow.populate_sink_selector() populates the combo box."""

    def test_shows_no_devices_message_when_empty(self, window: MainWindow) -> None:
        with patch(
            "live_translator.audio.virtual_speaker.VirtualSpeakerSource.list_sinks",
            return_value=[],
        ):
            window.populate_sink_selector()

        assert window._output_sink_combo.count() == 1
        assert "(No output devices found)" in window._output_sink_combo.itemText(0)
        assert window.get_output_sink() is None

    def test_populates_with_sinks(self, window: MainWindow) -> None:
        sinks = [
            {"name": "sink_1", "description": "First Sink"},
            {"name": "sink_2", "description": "Second Sink"},
        ]
        with patch(
            "live_translator.audio.virtual_speaker.VirtualSpeakerSource.list_sinks",
            return_value=sinks,
        ):
            window.populate_sink_selector()

        assert window._output_sink_combo.count() == 2
        assert window._output_sink_combo.itemData(0) == "sink_1"
        assert window._output_sink_combo.itemData(1) == "sink_2"

    def test_selects_saved_sink_from_config(self, window: MainWindow, config: ConfigManager) -> None:
        config.set("audio.virtual_speaker.output_sink", "sink_2")

        sinks = [
            {"name": "sink_1", "description": "First"},
            {"name": "sink_2", "description": "Second"},
            {"name": "sink_3", "description": "Third"},
        ]
        with patch(
            "live_translator.audio.virtual_speaker.VirtualSpeakerSource.list_sinks",
            return_value=sinks,
        ):
            window.populate_sink_selector()

        assert window._output_sink_combo.currentData() == "sink_2"

    def test_falls_back_to_default_sink(self, window: MainWindow) -> None:
        sinks = [
            {"name": "sink_a", "description": "A"},
            {"name": "sink_b", "description": "B"},
        ]
        with (
            patch(
                "live_translator.audio.virtual_speaker.VirtualSpeakerSource.list_sinks",
                return_value=sinks,
            ),
            patch(
                "live_translator.audio.virtual_speaker.VirtualSpeakerSource.get_default_sink_name",
                return_value="sink_b",
            ),
        ):
            window.populate_sink_selector()

        assert window._output_sink_combo.currentData() == "sink_b"

    def test_selects_first_sink_when_no_saved_and_no_default(self, window: MainWindow) -> None:
        sinks = [
            {"name": "sink_a", "description": "A"},
            {"name": "sink_b", "description": "B"},
        ]
        with (
            patch(
                "live_translator.audio.virtual_speaker.VirtualSpeakerSource.list_sinks",
                return_value=sinks,
            ),
            patch(
                "live_translator.audio.virtual_speaker.VirtualSpeakerSource.get_default_sink_name",
                return_value=None,
            ),
        ):
            window.populate_sink_selector()

        # First sink selected when no preferred one
        assert window._output_sink_combo.currentData() == "sink_a"


# ---------------------------------------------------------------------------
#  get_output_sink
# ---------------------------------------------------------------------------

class TestGetOutputSink:
    """MainWindow.get_output_sink() returns the correct value."""

    def test_returns_none_when_no_sinks(self, window: MainWindow) -> None:
        with patch(
            "live_translator.audio.virtual_speaker.VirtualSpeakerSource.list_sinks",
            return_value=[],
        ):
            window.populate_sink_selector()
        assert window.get_output_sink() is None

    def test_returns_selected_sink_name(self, window: MainWindow) -> None:
        sinks = [{"name": "my_sink", "description": "My Sink"}]
        with patch(
            "live_translator.audio.virtual_speaker.VirtualSpeakerSource.list_sinks",
            return_value=sinks,
        ):
            window.populate_sink_selector()
        assert window.get_output_sink() == "my_sink"
