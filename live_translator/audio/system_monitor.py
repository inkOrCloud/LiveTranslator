"""System audio output capture via PulseAudio monitor source."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import numpy as np
import sounddevice as sd  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class SystemMonitor:
    """Captures system audio output (speaker) using PulseAudio monitor.

    On Linux, this uses the PulseAudio monitor source. On other platforms
    it falls back to the default input device.
    """

    def __init__(self, sample_rate: int = 16000, channels: int = 1, blocksize: int = 1024) -> None:
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

        logger.debug(
            "SystemMonitor initialized: rate=%d, channels=%d, blocksize=%d",
            sample_rate,
            channels,
            blocksize,
        )

    def _find_monitor_device(self) -> int | None:
        """Find the PulseAudio monitor source device ID.

        Returns:
            Device index or None if no monitor found.
        """
        devices = sd.query_devices()
        logger.debug("Found %d audio device(s)", len(devices))
        for idx, dev in enumerate(devices):
            name: str = str(dev.get("name", ""))
            if "monitor" in name.lower():
                logger.info("Found PulseAudio monitor device: [%d] %s", idx, name)
                return int(idx)

        # Log available devices for debugging
        for idx, dev in enumerate(devices):
            logger.debug("  Device [%d]: %s (in=%d, out=%d)",
                         idx,
                         dev.get("name", "?"),
                         dev.get("max_input_channels", 0),
                         dev.get("max_output_channels", 0))

        logger.warning("No PulseAudio monitor device found, falling back to default input")
        return None

    def start(self, callback: Callable[[bytes], None]) -> None:
        """Start capturing system audio output.

        Args:
            callback: Called with PCM16 mono audio chunks.
        """
        self._callback = callback
        device = self._find_monitor_device()

        logger.info(
            "Starting audio capture: device=%s, rate=%d, channels=%d, blocksize=%d",
            device if device is not None else "default",
            self.sample_rate,
            self.channels,
            self.blocksize,
        )

        try:
            self._stream = sd.InputStream(
                device=device,
                samplerate=self.sample_rate,
                channels=self.channels,
                blocksize=self.blocksize,
                dtype=np.int16,
                callback=self._audio_callback,
            )
            self._stream.start()
            logger.info("Audio capture started successfully")
        except Exception:
            logger.exception("Failed to start audio capture")
            raise

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
        del frames, time_info

        # Log audio status issues
        if status:
            logger.warning("Audio callback status: %s", status)

        if self._callback and outdata.size > 0:
            self._callback(outdata.tobytes())

    def stop(self) -> None:
        """Stop capturing audio."""
        if self._stream is not None:
            logger.info("Stopping audio capture")
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                logger.exception("Error stopping audio stream")
            self._stream = None
        self._callback = None
        logger.debug("Audio capture stopped")

    @property
    def is_capturing(self) -> bool:
        """Whether the source is currently capturing."""
        return self._stream is not None and self._stream.active
