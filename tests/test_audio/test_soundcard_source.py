"""Tests for SoundcardSource."""
from __future__ import annotations
from typing import Protocol
from unittest.mock import ANY, MagicMock, patch
import numpy as np
import pytest
from live_translator.audio.source import AudioSource


class TestProtocolConformance:
    def test_is_importable(self):
        from live_translator.audio.soundcard_source import SoundcardSource
        assert SoundcardSource is not None

    def test_conforms_to_audio_source_protocol(self):
        from live_translator.audio.soundcard_source import SoundcardSource
        src = SoundcardSource()
        assert isinstance(src, AudioSource)

    def test_has_required_attributes(self):
        from live_translator.audio.soundcard_source import SoundcardSource
        src = SoundcardSource()
        assert hasattr(src, "sample_rate") and hasattr(src, "channels")
        assert hasattr(src, "start") and hasattr(src, "stop") and hasattr(src, "is_capturing")


class TestConstructor:
    def test_default_parameters(self):
        from live_translator.audio.soundcard_source import SoundcardSource
        src = SoundcardSource()
        assert src.sample_rate == 16000 and src.channels == 1
        assert src.blocksize == 2048 and src.device_name is None
        assert not src.is_capturing

    def test_custom_parameters(self):
        from live_translator.audio.soundcard_source import SoundcardSource
        src = SoundcardSource(device_name="My Loopback", sample_rate=44100, channels=2, blocksize=4096)
        assert src.device_name == "My Loopback" and src.sample_rate == 44100
        assert src.channels == 2 and src.blocksize == 4096 and not src.is_capturing


class TestConvertFormat:
    def test_float32_to_pcm16_normal(self):
        from live_translator.audio.soundcard_source import _float32_to_pcm16
        samples = np.array([0.0, 0.5, -0.5, 1.0, -1.0], dtype=np.float32)
        result = _float32_to_pcm16(samples)
        assert result == np.array([0, 16384, -16384, 32767, -32768], dtype=np.int16).tobytes()

    def test_float32_to_pcm16_clipping(self):
        from live_translator.audio.soundcard_source import _float32_to_pcm16
        samples = np.array([1.5, -2.0, 0.0], dtype=np.float32)
        result = _float32_to_pcm16(samples)
        assert result == np.array([32767, -32768, 0], dtype=np.int16).tobytes()

    def test_float32_to_pcm16_empty(self):
        from live_translator.audio.soundcard_source import _float32_to_pcm16
        assert _float32_to_pcm16(np.array([], dtype=np.float32)) == b""


class TestDownmix:
    def test_downmix_stereo_to_mono(self):
        from live_translator.audio.soundcard_source import _downmix_to_mono
        result = _downmix_to_mono(np.array([[0.0, 1.0], [0.5, 0.5], [0.0, 0.0], [-0.5, 0.5]], dtype=np.float32))
        np.testing.assert_array_almost_equal(result, np.array([0.5, 0.5, 0.0, 0.0], dtype=np.float32))

    def test_downmix_mono_unchanged(self):
        from live_translator.audio.soundcard_source import _downmix_to_mono
        samples = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        np.testing.assert_array_equal(_downmix_to_mono(samples), samples)

    def test_downmix_5chan_to_mono(self):
        from live_translator.audio.soundcard_source import _downmix_to_mono
        result = _downmix_to_mono(np.array([[1.0, 0.0, 0.5, 0.5, 0.0]], dtype=np.float32))
        np.testing.assert_array_almost_equal(result, np.array([0.4], dtype=np.float32))

    def test_downmix_empty(self):
        from live_translator.audio.soundcard_source import _downmix_to_mono
        assert _downmix_to_mono(np.array([], dtype=np.float32)).size == 0


class TestListDevices:
    def test_returns_empty_list_when_no_soundcard(self):
        from live_translator.audio.soundcard_source import SoundcardSource
        with patch.object(SoundcardSource, "_get_all_microphones", return_value=[]):
            assert SoundcardSource.list_devices() == []

    def test_returns_device_dicts(self):
        from live_translator.audio.soundcard_source import SoundcardSource
        mock_lb = MagicMock(); mock_lb.name = "Built-in Audio"; mock_lb.id = "monitor_id"
        mock_lb.channels = 2; mock_lb.isloopback = True
        mock_mic = MagicMock(); mock_mic.name = "Webcam Mic"; mock_mic.id = "mic_id"
        mock_mic.channels = 1; mock_mic.isloopback = False
        with patch.object(SoundcardSource, "_get_all_microphones", return_value=[mock_lb, mock_mic]):
            devices = SoundcardSource.list_devices()
        assert len(devices) == 2
        assert devices[0]["name"] == "Built-in Audio" and devices[0]["is_loopback"]
        assert devices[1]["name"] == "Webcam Mic" and not devices[1]["is_loopback"]


class TestStartStop:
    def test_start_auto_selects_loopback(self):
        from live_translator.audio.soundcard_source import SoundcardSource
        src = SoundcardSource()
        mock_mic = MagicMock(); mock_mic.name = "Monitor"; mock_mic.isloopback = True
        mock_rec = MagicMock(); mock_mic.recorder.return_value.__enter__.return_value = mock_rec
        with patch.object(src, "_select_device", return_value=mock_mic), patch.object(src, "_reader_loop"):
            src.start(MagicMock())
        assert src.is_capturing
        mock_mic.recorder.assert_called_once_with(samplerate=16000, channels=1, blocksize=2048)

    def test_start_ignored_when_already_capturing(self):
        from live_translator.audio.soundcard_source import SoundcardSource
        src = SoundcardSource(); src._capturing = True
        with patch.object(src, "_select_device") as m: src.start(MagicMock()); m.assert_not_called()

    def test_stop_cleans_up(self):
        from live_translator.audio.soundcard_source import SoundcardSource
        src = SoundcardSource(); src._capturing = True; src._stop_event = MagicMock()
        mock_ctx = MagicMock(); src._recorder_ctx = mock_ctx
        src.stop()
        assert not src.is_capturing; src._stop_event.set.assert_called_once()
        mock_ctx.__exit__.assert_called_once()

    def test_stop_noop_when_not_capturing(self):
        from live_translator.audio.soundcard_source import SoundcardSource
        src = SoundcardSource()
        with patch.object(src, "_stop_event") as m: src.stop(); m.set.assert_not_called()
