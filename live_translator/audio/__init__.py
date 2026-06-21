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
