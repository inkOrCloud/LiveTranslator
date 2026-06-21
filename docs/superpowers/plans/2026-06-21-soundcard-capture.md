# Soundcard Cross-Platform Audio Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace PulseAudio-only `VirtualSpeakerSource` with cross-platform `SoundcardSource` using the `soundcard` library.

**Architecture:** A new `SoundcardSource` class implements the existing `AudioSource` protocol. It uses `soundcard.all_microphones(include_loopback=True)` to find loopback (monitor) devices for capturing system audio output across Linux/macOS/Windows. Audio data flows as float32 numpy arrays from soundcard, converted to PCM16 int16 bytes for the existing callback pipeline.

**Tech Stack:** Python 3.12+, soundcard 0.4.6, numpy 2.x, PySide6

---

### Task 1: Update Configuration Defaults

**Files:**
- Modify: `live_translator/config/manager.py`
- Test: existing tests verify config loading

- [ ] **Step 1: Update `DEFAULT_CONFIG` in `config/manager.py`**

Replace the `audio.virtual_speaker` section with `audio.capture`:

```python
DEFAULT_CONFIG: dict[str, Any] = {
    "audio": {
        "sample_rate": 16000,
        "channels": 1,
        "capture": {
            "device_name": "",   # empty = auto-select default loopback
        },
    },
}
```

- [ ] **Step 2: Run existing config tests to verify no regression**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_config/ -v 2>&1`
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add live_translator/config/manager.py
git commit -m "chore: update config defaults for soundcard capture"
```

---

### Task 2: Create SoundcardSource (TDD)

**Files:**
- Create: `live_translator/audio/soundcard_source.py`
- Create: `tests/test_audio/test_soundcard_source.py`

- [ ] **Step 1: Write the test file `tests/test_audio/test_soundcard_source.py`**

```python
"""Tests for SoundcardSource."""

from __future__ import annotations

from typing import Protocol
from unittest.mock import ANY, MagicMock, patch

import numpy as np
import pytest

from live_translator.audio.source import AudioSource


class TestProtocolConformance:
    """SoundcardSource must implement the AudioSource protocol."""

    def test_is_importable(self) -> None:
        from live_translator.audio.soundcard_source import SoundcardSource
        assert SoundcardSource is not None

    def test_conforms_to_audio_source_protocol(self) -> None:
        from live_translator.audio.soundcard_source import SoundcardSource
        src = SoundcardSource()
        assert isinstance(src, AudioSource)

    def test_has_required_attributes(self) -> None:
        from live_translator.audio.soundcard_source import SoundcardSource
        src = SoundcardSource()
        assert hasattr(src, "sample_rate")
        assert hasattr(src, "channels")
        assert hasattr(src, "start")
        assert hasattr(src, "stop")
        assert hasattr(src, "is_capturing")


class TestConstructor:
    """SoundcardSource constructor parameter handling."""

    def test_default_parameters(self) -> None:
        from live_translator.audio.soundcard_source import SoundcardSource
        src = SoundcardSource()
        assert src.sample_rate == 16000
        assert src.channels == 1
        assert src.blocksize == 2048
        assert src.device_name is None
        assert not src.is_capturing

    def test_custom_parameters(self) -> None:
        from live_translator.audio.soundcard_source import SoundcardSource
        src = SoundcardSource(
            device_name="My Loopback",
            sample_rate=44100,
            channels=2,
            blocksize=4096,
        )
        assert src.device_name == "My Loopback"
        assert src.sample_rate == 44100
        assert src.channels == 2
        assert src.blocksize == 4096
        assert not src.is_capturing


class TestConvertFormat:
    """Float32 to PCM16 conversion."""

    def test_float32_to_pcm16_normal(self) -> None:
        from live_translator.audio.soundcard_source import _float32_to_pcm16
        samples = np.array([0.0, 0.5, -0.5, 1.0, -1.0], dtype=np.float32)
        result = _float32_to_pcm16(samples)
        # int16 values: 0, 16384, -16384, 32767, -32768
        expected = np.array([0, 16384, -16384, 32767, -32768], dtype=np.int16).tobytes()
        assert result == expected

    def test_float32_to_pcm16_clipping(self) -> None:
        from live_translator.audio.soundcard_source import _float32_to_pcm16
        samples = np.array([1.5, -2.0, 0.0], dtype=np.float32)
        result = _float32_to_pcm16(samples)
        expected = np.array([32767, -32768, 0], dtype=np.int16).tobytes()
        assert result == expected

    def test_float32_to_pcm16_empty(self) -> None:
        from live_translator.audio.soundcard_source import _float32_to_pcm16
        samples = np.array([], dtype=np.float32)
        result = _float32_to_pcm16(samples)
        assert result == b""


class TestDownmix:
    """Multi-channel to mono downmix."""

    def test_downmix_stereo_to_mono(self) -> None:
        from live_translator.audio.soundcard_source import _downmix_to_mono
        # 4 frames, 2 channels
        samples = np.array([[0.0, 1.0], [0.5, 0.5], [0.0, 0.0], [-0.5, 0.5]], dtype=np.float32)
        result = _downmix_to_mono(samples)
        expected = np.array([0.5, 0.5, 0.0, 0.0], dtype=np.float32)
        np.testing.assert_array_almost_equal(result, expected)

    def test_downmix_mono_unchanged(self) -> None:
        from live_translator.audio.soundcard_source import _downmix_to_mono
        samples = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        result = _downmix_to_mono(samples)
        np.testing.assert_array_equal(result, samples)

    def test_downmix_5chan_to_mono(self) -> None:
        from live_translator.audio.soundcard_source import _downmix_to_mono
        samples = np.array([[1.0, 0.0, 0.5, 0.5, 0.0]], dtype=np.float32)
        result = _downmix_to_mono(samples)
        expected = np.array([0.4], dtype=np.float32)
        np.testing.assert_array_almost_equal(result, expected)

    def test_downmix_empty(self) -> None:
        from live_translator.audio.soundcard_source import _downmix_to_mono
        samples = np.array([], dtype=np.float32)
        result = _downmix_to_mono(samples)
        assert result.size == 0


class TestListDevices:
    """SoundcardSource.list_devices() static method."""

    def test_returns_empty_list_when_no_soundcard(self) -> None:
        from live_translator.audio.soundcard_source import SoundcardSource
        with patch.object(SoundcardSource, "_get_all_microphones", return_value=[]):
            devices = SoundcardSource.list_devices()
        assert devices == []

    def test_returns_device_dicts(self) -> None:
        from live_translator.audio.soundcard_source import SoundcardSource

        mock_mic_loopback = MagicMock()
        mock_mic_loopback.name = "Built-in Audio Analog Stereo"
        mock_mic_loopback.id = "monitor_of_alsa_output.pci"
        mock_mic_loopback.channels = 2
        mock_mic_loopback.isloopback = True

        mock_mic_real = MagicMock()
        mock_mic_real.name = "Webcam Mic"
        mock_mic_real.id = "alsa_input.webcam"
        mock_mic_real.channels = 1
        mock_mic_real.isloopback = False

        with patch.object(SoundcardSource, "_get_all_microphones", return_value=[mock_mic_loopback, mock_mic_real]):
            devices = SoundcardSource.list_devices()

        assert len(devices) == 2
        assert devices[0]["name"] == "Built-in Audio Analog Stereo"
        assert devices[0]["id"] == "monitor_of_alsa_output.pci"
        assert devices[0]["channels"] == 2
        assert devices[0]["is_loopback"] is True

        assert devices[1]["name"] == "Webcam Mic"
        assert devices[1]["is_loopback"] is False


class TestStartStop:
    """High-level start/stop with soundcard mocked."""

    def test_start_auto_selects_loopback(self) -> None:
        from live_translator.audio.soundcard_source import SoundcardSource

        src = SoundcardSource()

        mock_mic = MagicMock()
        mock_mic.name = "Monitor of Built-in Audio"
        mock_mic.isloopback = True
        mock_recorder = MagicMock()
        mock_mic.recorder.return_value.__enter__.return_value = mock_recorder

        with (
            patch.object(src, "_select_device", return_value=mock_mic),
            patch.object(src, "_reader_loop"),
        ):
            callback = MagicMock()
            src.start(callback)

        assert src.is_capturing
        mock_mic.recorder.assert_called_once_with(
            samplerate=16000, channels=1, blocksize=2048,
        )

    def test_start_ignored_when_already_capturing(self) -> None:
        from live_translator.audio.soundcard_source import SoundcardSource
        src = SoundcardSource()
        src._capturing = True
        with patch.object(src, "_select_device") as mock_select:
            src.start(MagicMock())
        mock_select.assert_not_called()

    def test_stop_cleans_up(self) -> None:
        from live_translator.audio.soundcard_source import SoundcardSource
        src = SoundcardSource()
        src._capturing = True
        src._stop_event = MagicMock()
        mock_rec_ctx = MagicMock()
        src._recorder_ctx = mock_rec_ctx

        src.stop()

        assert not src.is_capturing
        src._stop_event.set.assert_called_once()
        mock_rec_ctx.__exit__.assert_called_once()

    def test_stop_noop_when_not_capturing(self) -> None:
        from live_translator.audio.soundcard_source import SoundcardSource
        src = SoundcardSource()
        with patch.object(src, "_stop_event") as mock_event:
            src.stop()
        mock_event.set.assert_not_called()
```

- [ ] **Step 2: Run the test file to confirm failures**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_audio/test_soundcard_source.py -v 2>&1`
Expected: ImportError or ModuleNotFoundError for SoundcardSource (tests don't exist yet).

- [ ] **Step 3: Write the SoundcardSource implementation in `live_translator/audio/soundcard_source.py`**

```python
"""System audio capture using the ``soundcard`` library.

Captures system audio output (speaker loopback) by using ``soundcard``
to list microphone/loopback devices and recording from a selected
loopback monitor source.

Cross-platform: Linux (PulseAudio), macOS (CoreAudio), Windows (MediaFoundation).
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def _float32_to_pcm16(samples: np.ndarray) -> bytes:
    """Convert float32 [-1, 1] array to PCM16 int16 bytes.

    Args:
        samples: Float32 numpy array of audio samples.

    Returns:
        PCM16 bytes (int16 little-endian).
    """
    if samples.size == 0:
        return b""
    samples = np.clip(samples, -1.0, 1.0)
    pcm16 = (samples * 32767).astype(np.int16)
    return pcm16.tobytes()


def _downmix_to_mono(samples: np.ndarray) -> np.ndarray:
    """Downmix multi-channel audio to mono by averaging channels.

    Args:
        samples: Float32 numpy array of shape (frames, channels) or (frames,).

    Returns:
        Mono float32 array of shape (frames,).
    """
    if samples.ndim == 1:
        return samples
    if samples.size == 0:
        return np.array([], dtype=np.float32)
    return samples.mean(axis=1, dtype=np.float32)


class SoundcardSource:
    """Captures system audio output using the ``soundcard`` library.

    Implements the :class:`~live_translator.audio.source.AudioSource` protocol.

    On :meth:`start`, selects a loopback device (the default speaker's monitor
    source) via ``soundcard`` and begins recording in a background thread.
    Audio chunks are converted from float32 to PCM16 int16 bytes and delivered
    to the callback.
    """

    def __init__(
        self,
        device_name: str | None = None,
        sample_rate: int = 16000,
        channels: int = 1,
        blocksize: int = 2048,
    ) -> None:
        """Initialize the soundcard capture source.

        Args:
            device_name: Name or substring of the device to use, or ``None``
                to auto-select the default speaker's loopback.
            sample_rate: Target sample rate in Hz (default: 16000).
            channels: Output channel count (default: 1 for mono).
            blocksize: Internal capture buffer size (default: 2048).
        """
        self.device_name = device_name
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize

        self._capturing = False
        self._callback: Callable[[bytes], None] | None = None
        self._stop_event = threading.Event()
        self._reader_thread: threading.Thread | None = None
        self._recorder_ctx: Any = None  # context manager from mic.recorder()
        self._selected_mic: Any = None

        logger.debug(
            "SoundcardSource initialized: device=%s, rate=%d, channels=%d, blocksize=%d",
            device_name or "(auto)",
            sample_rate,
            channels,
            blocksize,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, callback: Callable[[bytes], None]) -> None:
        """Start capturing system audio.

        Args:
            callback: Called with PCM16 mono audio chunks.

        Raises:
            RuntimeError: If ``soundcard`` is not available or no suitable
                device is found.
        """
        if self._capturing:
            logger.warning("SoundcardSource already capturing, ignoring start")
            return

        self._callback = callback
        self._stop_event.clear()

        mic = self._select_device()
        if mic is None:
            msg = "No suitable audio capture device found"
            logger.error(msg)
            raise RuntimeError(msg)

        self._selected_mic = mic
        logger.info(
            "Selected capture device: %s (loopback=%s, channels=%d)",
            mic.name,
            getattr(mic, "isloopback", False),
            getattr(mic, "channels", "?"),
        )

        # Open recorder context manager
        self._recorder_ctx = mic.recorder(
            samplerate=self.sample_rate,
            channels=self.channels,
            blocksize=self.blocksize,
        )
        recorder = self._recorder_ctx.__enter__()

        # Start reader thread
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            args=(recorder,),
            name="soundcard-reader",
            daemon=True,
        )
        self._reader_thread.start()

        self._capturing = True
        logger.info(
            "Soundcard capture started: device=%s, rate=%d, channels=%d",
            mic.name,
            self.sample_rate,
            self.channels,
        )

    def stop(self) -> None:
        """Stop capturing and release the audio device."""
        if not self._capturing:
            logger.debug("SoundcardSource not capturing, ignoring stop")
            return

        self._capturing = False
        self._stop_event.set()

        # Close recorder context manager
        if self._recorder_ctx is not None:
            try:
                self._recorder_ctx.__exit__(None, None, None)
            except Exception:
                logger.exception("Error closing recorder")
            self._recorder_ctx = None

        # Wait for reader thread
        if self._reader_thread is not None and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=3)
        self._reader_thread = None

        self._callback = None
        self._selected_mic = None
        logger.info("Soundcard capture stopped")

    @property
    def is_capturing(self) -> bool:
        """Whether audio is currently being captured."""
        return self._capturing

    # ------------------------------------------------------------------
    # Device enumeration (public)
    # ------------------------------------------------------------------

    @staticmethod
    def list_devices() -> list[dict[str, Any]]:
        """List available audio capture devices.

        Returns a list of dicts with keys:
        - ``name``: human-readable device name
        - ``id``: soundcard device ID
        - ``channels``: number of input channels
        - ``is_loopback``: whether this is a loopback (monitor) device

        Returns:
            List of device dicts, or empty list if ``soundcard`` is unavailable.
        """
        try:
            mics = SoundcardSource._get_all_microphones()
        except Exception:
            logger.exception("Failed to list soundcard devices")
            return []

        devices: list[dict[str, Any]] = []
        for mic in mics:
            devices.append({
                "name": getattr(mic, "name", "Unknown"),
                "id": getattr(mic, "id", ""),
                "channels": getattr(mic, "channels", 0),
                "is_loopback": getattr(mic, "isloopback", False),
            })
        return devices

    @staticmethod
    def _get_all_microphones():
        """Import soundcard and return ``all_microphones(include_loopback=True)``."""
        import soundcard as sc
        return sc.all_microphones(include_loopback=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _select_device(self):
        """Select the target microphone device.

        Returns a soundcard ``_Microphone`` instance, or ``None``.
        """
        import soundcard as sc

        mics = sc.all_microphones(include_loopback=True)
        if not mics:
            logger.error("No audio input devices found")
            return None

        # If a specific device name was requested, try to match it
        if self.device_name:
            try:
                return sc.get_microphone(self.device_name, include_loopback=True)
            except Exception:
                logger.warning(
                    "Requested device '%s' not found, falling back to auto-select",
                    self.device_name,
                )

        # Auto-select: prefer loopback of the default speaker
        loopbacks = [m for m in mics if getattr(m, "isloopback", False)]
        if loopbacks:
            try:
                default_speaker = sc.default_speaker()
                default_name = default_speaker.name
                # Find matching loopback
                for lb in loopbacks:
                    if default_name in lb.name or lb.name in default_name:
                        logger.info("Auto-selected loopback: %s", lb.name)
                        return lb
            except Exception:
                logger.debug("Could not get default speaker, using first loopback")

            # Fallback to first loopback
            logger.info("Using first available loopback: %s", loopbacks[0].name)
            return loopbacks[0]

        # No loopback found, use default microphone
        logger.warning("No loopback device found, falling back to default microphone")
        try:
            return sc.default_microphone()
        except Exception:
            logger.error("No microphone available either")
            return None

    def _reader_loop(self, recorder) -> None:
        """Continuously read audio chunks from the recorder.

        Args:
            recorder: A soundcard ``_Recorder`` instance.
        """
        logger.debug("Soundcard reader thread started")
        try:
            while not self._stop_event.is_set():
                try:
                    chunk = recorder.record(numframes=None)
                except Exception:
                    if not self._stop_event.is_set():
                        logger.exception("Error reading audio from recorder")
                    break

                if chunk is None or chunk.size == 0:
                    continue

                # Downmix to mono if needed
                if chunk.ndim > 1 and chunk.shape[1] > 1:
                    chunk = _downmix_to_mono(chunk)

                # Convert to PCM16 bytes
                pcm16_bytes = _float32_to_pcm16(chunk)

                if self._callback and len(pcm16_bytes) > 0:
                    self._callback(pcm16_bytes)

        except Exception:
            logger.exception("Fatal error in soundcard reader thread")
        finally:
            logger.debug("Soundcard reader thread exiting")

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> SoundcardSource:
        """Context manager entry (does not auto-start)."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Context manager exit: ensures cleanup."""
        self.stop()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_audio/test_soundcard_source.py -v 2>&1`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add live_translator/audio/soundcard_source.py tests/test_audio/test_soundcard_source.py
git commit -m "feat: add SoundcardSource for cross-platform audio capture"
```

---

### Task 3: Update Audio Module Exports

**Files:**
- Modify: `live_translator/audio/__init__.py`

- [ ] **Step 1: Update `live_translator/audio/__init__.py`**

```python
"""Audio capture module for LiveTranslator.

Provides audio source implementations for capturing system audio
using the cross-platform ``soundcard`` library.
"""

from live_translator.audio.soundcard_source import SoundcardSource
from live_translator.audio.source import AudioSource

__all__ = [
    "AudioSource",
    "SoundcardSource",
]
```

- [ ] **Step 2: Verify import works**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run python3 -c "from live_translator.audio import SoundcardSource, AudioSource; print('OK')" 2>&1`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add live_translator/audio/__init__.py
git commit -m "chore: update audio module exports for SoundcardSource"
```

---

### Task 4: Remove VirtualSpeakerSource

**Files:**
- Delete: `live_translator/audio/virtual_speaker.py`
- Delete: `tests/test_audio/test_virtual_speaker.py`

- [ ] **Step 1: Remove old files**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && rm live_translator/audio/virtual_speaker.py tests/test_audio/test_virtual_speaker.py`

- [ ] **Step 2: Verify nothing imports VirtualSpeakerSource anymore**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && grep -r "VirtualSpeakerSource" --include="*.py" | grep -v ".venv" | grep -v ".git" 2>&1`
Expected: No output (no references remain).

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: remove VirtualSpeakerSource (replaced by SoundcardSource)"
```

---

### Task 5: Update GUI Main Window

**Files:**
- Modify: `live_translator/gui/main_window.py`

- [ ] **Step 1: Update imports in `main_window.py`**

Remove the `VirtualSpeakerSource` import. Add `SoundcardSource` import:

```python
# Replace:
from live_translator.audio.virtual_speaker import VirtualSpeakerSource

# With:
from live_translator.audio.soundcard_source import SoundcardSource
```

- [ ] **Step 2: Update the UI building method in `main_window.py`**

Replace the "Output Device" section in `_build_ui()`:

```python
# === Capture device selector ===
output_layout = QHBoxLayout()
output_layout.addWidget(QLabel("Capture Device:"))
self._output_sink_combo = QComboBox()
self._output_sink_combo.setMinimumWidth(180)
output_layout.addWidget(self._output_sink_combo, stretch=1)
layout.addLayout(output_layout)
```

Remove the `_btn_refresh_sinks` attribute entirely (no refresh button needed).

- [ ] **Step 3: Update `populate_sink_selector()` method**

Rename to `populate_capture_devices()` and use `SoundcardSource.list_devices()`:

```python
def populate_capture_devices(self) -> None:
    """Populate the capture device selector from soundcard."""
    self._output_sink_combo.clear()

    devices = SoundcardSource.list_devices()

    if not devices:
        self._output_sink_combo.addItem("(No devices found)", None)
        logger.warning("No audio capture devices found")
        return

    for dev in devices:
        label = dev["name"]
        if dev["channels"]:
            label += f" ({dev['channels']}ch)"
        label += " [Loopback]" if dev["is_loopback"] else " [Mic]"
        self._output_sink_combo.addItem(label, dev["id"])

    # Select saved device from config
    saved = self._config.get("audio.capture.device_name", "")
    if saved:
        idx = self._output_sink_combo.findData(saved)
        if idx >= 0:
            self._output_sink_combo.setCurrentIndex(idx)
            logger.debug("Selected saved capture device: %s", saved)
            return

    # Select first loopback device by default
    for i in range(self._output_sink_combo.count()):
        txt = self._output_sink_combo.itemText(i)
        if "[Loopback]" in txt:
            self._output_sink_combo.setCurrentIndex(i)
            logger.debug("Auto-selected first loopback device")
            return
```

- [ ] **Step 4: Update `get_output_sink()` method**

Rename to `get_capture_device()`:

```python
def get_capture_device(self) -> str | None:
    """Get the currently selected capture device ID.

    Returns:
        Device ID string, or ``None`` if no device selected.
    """
    data = self._output_sink_combo.currentData()
    return str(data) if data and str(data) != "None" else None
```

- [ ] **Step 5: Commit**

```bash
git add live_translator/gui/main_window.py
git commit -m "feat: update main window for soundcard capture device selection"
```

---

### Task 6: Update GUI Tests

**Files:**
- Modify: `tests/test_gui/test_output_device.py`

- [ ] **Step 1: Rewrite `tests/test_gui/test_output_device.py`**

```python
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


# ---------------------------------------------------------------------------
#  UI element presence
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
#  populate_capture_devices
# ---------------------------------------------------------------------------

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
        # First should be the loopback (sorted by original order)
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

        # Should select the loopback
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


# ---------------------------------------------------------------------------
#  get_capture_device
# ---------------------------------------------------------------------------

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
```

- [ ] **Step 2: Run tests to verify**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gui/test_output_device.py -v 2>&1`
Expected: All tests pass (some may fail initially if the main_window changes aren't complete yet, but after Step 5's main_window changes they will pass).

- [ ] **Step 3: Commit**

```bash
git add tests/test_gui/test_output_device.py
git commit -m "chore: update GUI tests for soundcard capture device selection"
```

---

### Task 7: Update App Wiring

**Files:**
- Modify: `live_translator/gui/app.py`

- [ ] **Step 1: Update `_rebuild_pipeline()` in `app.py`**

Replace the VirtualSpeakerSource construction with SoundcardSource:

```python
def _rebuild_pipeline(self) -> None:
    # ... existing service selection code ...

    from live_translator.audio.soundcard_source import SoundcardSource

    sample_rate = self._config.get("audio.sample_rate", 16000)

    # Determine the capture device from the GUI selection or config
    device_name = None
    if self._main_window:
        device_name = self._main_window.get_capture_device()

    audio = SoundcardSource(
        device_name=device_name,
        sample_rate=sample_rate,
    )
    logger.info(
        "Using SoundcardSource: device_name=%s",
        device_name or "(auto)",
    )

    # ... rest of pipeline creation ...
```

- [ ] **Step 2: Update the `run()` method to use new method name**

Replace `self._main_window.populate_sink_selector()` with `self._main_window.populate_capture_devices()`:

```python
# Replace:
self._main_window.populate_sink_selector()

# With:
self._main_window.populate_capture_devices()
```

Remove the refresh button signal wiring:

```python
# Remove this line:
self._main_window._btn_refresh_sinks.clicked.connect(
    self._main_window.populate_sink_selector,
)
```

- [ ] **Step 3: Update `_on_start()` to use new getter**

In `_on_start()`, remove the explicit `_rebuild_pipeline()` comment about output_sink_name — it's now about capture device.

- [ ] **Step 4: Run all tests to verify no regressions**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest -v 2>&1`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add live_translator/gui/app.py
git commit -m "feat: update app wiring to use SoundcardSource"
```

---

### Task 8: Update Dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Update `pyproject.toml` dependencies**

Replace `sounddevice` with `soundcard`:

```toml
dependencies = [
    "litellm>=1.87.1",
    "numpy>=2.4.6",
    "pyside6>=6.11.1",
    "requests>=2.34.2",
    "soundcard>=0.4.6",
    "websockets>=16.0",
]
```

- [ ] **Step 2: Sync dependencies and verify**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv sync 2>&1`

Expected: Dependencies resolve and install successfully.

- [ ] **Step 3: Run full test suite**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest -v 2>&1`
Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: replace sounddevice with soundcard in dependencies"
```
