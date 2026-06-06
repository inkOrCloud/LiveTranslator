"""Tests for audio source abstraction."""

from __future__ import annotations

from typing import Protocol

from live_translator.audio.source import AudioSource


def test_audio_source_importable() -> None:
    """AudioSource protocol should be importable."""
    assert AudioSource is not None


def test_audio_source_is_protocol() -> None:
    """AudioSource should be a Protocol class."""
    assert issubclass(AudioSource, Protocol)
