"""Tests for capture device selection in MainWindow."""

from __future__ import annotations

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


class TestCaptureDeviceUI:
    """The capture device selector UI elements exist."""

    def test_has_output_sink_combo(self, window: MainWindow) -> None:
        assert hasattr(window, "_output_sink_combo")

    def test_has_populate_method(self, window: MainWindow) -> None:
        assert hasattr(window, "populate_capture_devices")
        assert callable(window.populate_capture_devices)

    def test_has_get_capture_device_method(self, window: MainWindow) -> None:
        assert hasattr(window, "get_capture_device")
        assert callable(window.get_capture_device)


class TestPopulateCaptureDevices:
    """MainWindow.populate_capture_devices() populates the combo box."""

    def test_shows_no_devices_message_when_empty(self, window: MainWindow) -> None:
        with patch(
            "live_translator.audio.soundcard_source.SoundcardSource.list_devices",
            return_value=[],
        ):
            window.populate_capture_devices()

        assert window._output_sink_combo.count() == 1
        assert "(No devices found)" in window._output_sink_combo.itemText(0)
        assert window.get_capture_device() is None

    def test_populates_with_devices(self, window: MainWindow) -> None:
        devices = [
            {"name": "Loopback Device", "id": "monitor_id_1", "channels": 2, "is_loopback": True},
            {"name": "Webcam Mic", "id": "mic_id_1", "channels": 1, "is_loopback": False},
        ]
        with patch(
            "live_translator.audio.soundcard_source.SoundcardSource.list_devices",
            return_value=devices,
        ):
            window.populate_capture_devices()

        assert window._output_sink_combo.count() == 2
        assert window._output_sink_combo.itemData(0) == "monitor_id_1"
        assert window._output_sink_combo.itemData(1) == "mic_id_1"

    def test_selects_saved_device_from_config(self, window: MainWindow) -> None:
        window._config.set("audio.capture.device_name", "mic_id_1")

        devices = [
            {"name": "Loopback", "id": "loopback_1", "channels": 2, "is_loopback": True},
            {"name": "Mic", "id": "mic_id_1", "channels": 1, "is_loopback": False},
            {"name": "Loopback 2", "id": "loopback_2", "channels": 2, "is_loopback": True},
        ]
        with patch(
            "live_translator.audio.soundcard_source.SoundcardSource.list_devices",
            return_value=devices,
        ):
            window.populate_capture_devices()

        assert window.get_capture_device() == "mic_id_1"

    def test_prefers_loopback_when_no_saved_config(self, window: MainWindow) -> None:
        devices = [
            {"name": "Mic", "id": "mic_1", "channels": 1, "is_loopback": False},
            {"name": "Loopback", "id": "lb_1", "channels": 2, "is_loopback": True},
        ]
        with patch(
            "live_translator.audio.soundcard_source.SoundcardSource.list_devices",
            return_value=devices,
        ):
            window.populate_capture_devices()

        assert window.get_capture_device() == "lb_1"

    def test_selects_first_when_no_loopback(self, window: MainWindow) -> None:
        devices = [
            {"name": "Mic A", "id": "mic_a", "channels": 1, "is_loopback": False},
            {"name": "Mic B", "id": "mic_b", "channels": 1, "is_loopback": False},
        ]
        with patch(
            "live_translator.audio.soundcard_source.SoundcardSource.list_devices",
            return_value=devices,
        ):
            window.populate_capture_devices()

        assert window.get_capture_device() == "mic_a"


class TestGetCaptureDevice:
    """MainWindow.get_capture_device() returns the correct value."""

    def test_returns_none_when_no_devices(self, window: MainWindow) -> None:
        with patch(
            "live_translator.audio.soundcard_source.SoundcardSource.list_devices",
            return_value=[],
        ):
            window.populate_capture_devices()
        assert window.get_capture_device() is None

    def test_returns_selected_device_id(self, window: MainWindow) -> None:
        devices = [{"name": "My Device", "id": "device_42", "channels": 2, "is_loopback": True}]
        with patch(
            "live_translator.audio.soundcard_source.SoundcardSource.list_devices",
            return_value=devices,
        ):
            window.populate_capture_devices()
        assert window.get_capture_device() == "device_42"
