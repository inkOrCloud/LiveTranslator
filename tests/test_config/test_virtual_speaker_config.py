"""Tests for virtual speaker config defaults."""

from __future__ import annotations

from live_translator.config.manager import DEFAULT_CONFIG


class TestVirtualSpeakerConfigDefaults:
    """Default config contains virtual speaker settings."""

    def test_audio_section_exists(self) -> None:
        assert "audio" in DEFAULT_CONFIG

    def test_virtual_speaker_section_exists(self) -> None:
        assert "virtual_speaker" in DEFAULT_CONFIG["audio"]

    def test_has_output_sink_default(self) -> None:
        assert "output_sink" in DEFAULT_CONFIG["audio"]["virtual_speaker"]
        assert DEFAULT_CONFIG["audio"]["virtual_speaker"]["output_sink"] == ""

    def test_has_sink_name_default(self) -> None:
        assert DEFAULT_CONFIG["audio"]["virtual_speaker"]["sink_name"] == "LiveTranslatorVirtualSpeaker"

    def test_has_sink_description_default(self) -> None:
        assert DEFAULT_CONFIG["audio"]["virtual_speaker"]["sink_description"] == "LiveTranslator Virtual Speaker"

    def test_has_sample_rate_default(self) -> None:
        assert DEFAULT_CONFIG["audio"]["sample_rate"] == 16000

    def test_has_channels_default(self) -> None:
        assert DEFAULT_CONFIG["audio"]["channels"] == 1
