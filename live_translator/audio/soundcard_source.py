"""System audio capture using the soundcard library.

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
    """Convert float32 samples (-1.0 to 1.0) to PCM16 bytes."""
    if samples.size == 0:
        return b""
    return (np.clip(samples * 32768, -32768, 32767)).astype(np.int16).tobytes()


def _downmix_to_mono(samples: np.ndarray) -> np.ndarray:
    """Downmix multi-channel audio to mono by averaging channels."""
    if samples.ndim == 1:
        return samples
    if samples.size == 0:
        return np.array([], dtype=np.float32)
    return samples.mean(axis=1, dtype=np.float32)


class SoundcardSource:
    """Audio source that captures system audio using the soundcard library."""

    def __init__(
        self,
        device_name: str | None = None,
        sample_rate: int = 16000,
        channels: int = 1,
        blocksize: int = 2048,
    ):
        self.device_name = device_name
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize
        self._capturing = False
        self._callback: Callable[[bytes], None] | None = None
        self._stop_event = threading.Event()
        self._reader_thread: threading.Thread | None = None
        self._recorder_ctx: Any = None
        self._selected_mic: Any = None

    @property
    def is_capturing(self) -> bool:
        return self._capturing

    def start(self, callback: Callable[[bytes], None]) -> None:
        """Start capturing audio.

        Args:
            callback: Called with PCM16 mono audio chunks.

        Raises:
            RuntimeError: If no suitable audio device is found.
        """
        if self._capturing:
            return
        self._callback = callback
        self._stop_event.clear()
        mic = self._select_device()
        if mic is None:
            raise RuntimeError("No suitable audio capture device found")
        self._selected_mic = mic
        self._recorder_ctx = mic.recorder(
            samplerate=self.sample_rate,
            channels=self.channels,
            blocksize=self.blocksize,
        )
        recorder = self._recorder_ctx.__enter__()
        self._reader_thread = threading.Thread(
            target=self._reader_loop, args=(recorder,), daemon=True
        )
        self._reader_thread.start()
        self._capturing = True

    def stop(self) -> None:
        """Stop capturing audio and clean up resources."""
        if not self._capturing:
            return
        self._capturing = False
        self._stop_event.set()
        if self._recorder_ctx is not None:
            try:
                self._recorder_ctx.__exit__(None, None, None)
            except Exception:
                logger.exception("Error closing recorder")
            self._recorder_ctx = None
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=3)
        self._reader_thread = None
        self._callback = None
        self._selected_mic = None

    @staticmethod
    def list_devices() -> list[dict[str, Any]]:
        """List available audio capture devices.

        Returns:
            List of dicts with name, id, channels, and is_loopback keys.
        """
        try:
            mics = SoundcardSource._get_all_microphones()
        except Exception:
            return []
        return [
            {
                "name": getattr(m, "name", "Unknown"),
                "id": getattr(m, "id", ""),
                "channels": getattr(m, "channels", 0),
                "is_loopback": getattr(m, "isloopback", False),
            }
            for m in mics
        ]

    @staticmethod
    def _get_all_microphones():
        import soundcard as sc

        return sc.all_microphones(include_loopback=True)

    def _select_device(self):
        """Select the best available microphone/loopback device."""
        import soundcard as sc

        mics = sc.all_microphones(include_loopback=True)
        if not mics:
            return None
        if self.device_name:
            try:
                return sc.get_microphone(self.device_name, include_loopback=True)
            except Exception:
                pass
        loopbacks = [m for m in mics if getattr(m, "isloopback", False)]
        if loopbacks:
            try:
                default = sc.default_speaker().name
                for lb in loopbacks:
                    if default in lb.name or lb.name in default:
                        return lb
            except Exception:
                pass
            return loopbacks[0]
        try:
            return sc.default_microphone()
        except Exception:
            return None

    def _reader_loop(self, recorder):
        """Background thread that reads audio chunks and calls the callback."""
        while not self._stop_event.is_set():
            try:
                chunk = recorder.record(numframes=None)
            except Exception:
                break
            if chunk is None or chunk.size == 0:
                continue
            if chunk.ndim > 1 and chunk.shape[1] > 1:
                chunk = _downmix_to_mono(chunk)
            pcm16 = _float32_to_pcm16(chunk)
            if self._callback and len(pcm16) > 0:
                self._callback(pcm16)

    def __enter__(self) -> "SoundcardSource":
        return self

    def __exit__(self, *args):
        self.stop()
