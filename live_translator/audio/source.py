"""Abstract interface for audio sources."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable


@runtime_checkable
class AudioSource(Protocol):
    """Protocol for audio input sources.

    Implementations capture audio from system output (monitor), microphone,
    or other sources and deliver raw PCM16 chunks via a callback.
    """

    sample_rate: int
    channels: int

    def start(self, callback: Callable[[bytes], None]) -> None:
        """Start capturing audio.

        Args:
            callback: Called with PCM16 mono audio chunks.
        """
        ...

    def stop(self) -> None:
        """Stop capturing audio."""
        ...

    @property
    def is_capturing(self) -> bool:
        """Whether the source is currently capturing."""
        ...
