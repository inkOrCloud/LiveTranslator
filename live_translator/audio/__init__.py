"""Audio capture module for LiveTranslator.

Provides audio source implementations for capturing system audio
via a virtual PulseAudio speaker.
"""

from live_translator.audio.source import AudioSource
from live_translator.audio.virtual_speaker import VirtualSpeakerSource

__all__ = [
    "AudioSource",
    "VirtualSpeakerSource",
]
