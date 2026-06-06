"""System audio output capture via PulseAudio monitor source."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import sounddevice as sd


class SystemMonitor:
    """Captures system audio output (speaker) using PulseAudio monitor.

    On Linux, this uses the PulseAudio monitor source. On other platforms
    it falls back to the default input device.
    """

    def __init__(self, sample_rate: int = 16000,
                 channels: int = 1,
                 blocksize: int = 1024) -> None:
        """Initialize system audio monitor.

        Args:
            sample_rate: Target sample rate in Hz (default: 16000).
            channels: Number of channels (default: 1 for mono).
            blocksize: Audio buffer block size (default: 1024).
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize
        self._stream: sd.InputStream | None = None
        self._callback: Callable[[bytes], None] | None = None

    def _find_monitor_device(self) -> int | None:
        """Find the PulseAudio monitor source device ID.

        Returns:
            Device index or None if no monitor found.
        """
        devices = sd.query_devices()
        for idx, dev in enumerate(devices):
            name: str = str(dev.get("name", ""))
            if "monitor" in name.lower():
                return int(idx)
        return None

    def start(self, callback: Callable[[bytes], None]) -> None:
        """Start capturing system audio output.

        Args:
            callback: Called with PCM16 mono audio chunks.
        """
        self._callback = callback
        device = self._find_monitor_device()

        self._stream = sd.InputStream(
            device=device,
            samplerate=self.sample_rate,
            channels=self.channels,
            blocksize=self.blocksize,
            dtype=np.int16,
            callback=self._audio_callback,
        )
        self._stream.start()

    def _audio_callback(
        self,
        outdata: np.ndarray,
        frames: int,
        time_info: Any,
        status: sd.CallbackFlags,
    ) -> None:
        """Callback from sounddevice InputStream.

        Args:
            outdata: Audio data buffer (written in-place).
            frames: Number of frames.
            time_info: Time info dict.
            status: Status flags.
        """
        del frames, time_info, status
        if self._callback and outdata.size > 0:
            chunk = outdata.tobytes()
            self._callback(chunk)

    def stop(self) -> None:
        """Stop capturing audio."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._callback = None

    @property
    def is_capturing(self) -> bool:
        """Whether the source is currently capturing."""
        return self._stream is not None and self._stream.active
