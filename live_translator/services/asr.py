"""Abstract interfaces for streaming ASR services."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ASRSession(Protocol):
    """A streaming speech recognition session."""

    def send_audio(self, chunk: bytes) -> None:
        """Send an audio chunk (PCM16, 16kHz, mono) for recognition.

        Args:
            chunk: Raw PCM16 mono audio data at 16kHz.
        """
        ...

    def on_partial(self, callback: Callable[[str], None]) -> None:
        """Register a callback for partial (in-progress) transcription.

        Args:
            callback: Called with partial transcription string.
        """
        ...

    def on_final(self, callback: Callable[[str], None]) -> None:
        """Register a callback for final (confirmed) transcription.

        Args:
            callback: Called with final transcription string.
        """
        ...

    def on_error(self, callback: Callable[[Exception], None]) -> None:
        """Register a callback for session errors.

        Args:
            callback: Called with the exception that occurred.
        """
        ...

    def close(self) -> None:
        """Close the session and release resources."""
        ...

    @property
    def is_alive(self) -> bool:
        """Whether the session connection is still active."""
        ...


@runtime_checkable
class SpeechRecognizer(Protocol):
    """Factory interface for creating streaming ASR sessions."""

    service_id: str
    """Unique identifier for this service."""

    display_name: str
    """Human-readable name for UI."""

    config: dict[str, Any]
    """Current configuration dict for this service instance."""

    def create_session(self) -> ASRSession:
        """Create a new streaming recognition session.

        Returns:
            An ASRSession ready to receive audio data.
        """
        ...

    @classmethod
    def config_schema(cls) -> dict[str, Any]:
        """Return JSON Schema (Draft 07) for the config fields.

        Returns:
            A JSON Schema dict.
        """
        ...
