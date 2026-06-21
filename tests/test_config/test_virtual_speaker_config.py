"""Tests for audio capture config defaults."""

from __future__ import annotations

from live_translator.config.manager import DEFAULT_CONFIG


class TestAudioCaptureConfigDefaults:
    """Default config contains audio capture settings."""

    def test_audio_section_exists(self) -> None:
        assert "audio" in DEFAULT_CONFIG

    def test_capture_section_exists(self) -> None:
        assert "capture" in DEFAULT_CONFIG["audio"]

    def test_has_device_name_default(self) -> None:
        assert "device_name" in DEFAULT_CONFIG["audio"]["capture"]
        assert DEFAULT_CONFIG["audio"]["capture"]["device_name"] == ""

    def test_has_sample_rate_default(self) -> None:
        assert DEFAULT_CONFIG["audio"]["sample_rate"] == 16000

    def test_has_channels_default(self) -> None:
        assert DEFAULT_CONFIG["audio"]["channels"] == 1
