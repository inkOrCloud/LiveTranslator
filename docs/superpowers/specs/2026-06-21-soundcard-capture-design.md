# SoundcardSource: Cross-Platform System Audio Capture

- **Date**: 2026-06-21
- **Status**: Approved Design
- **Goal**: Replace PulseAudio-only `VirtualSpeakerSource` with `soundcard`-based
  cross-platform system audio capture.

## Motivation

The current `VirtualSpeakerSource` uses PulseAudio-specific commands
(`pactl`, `parec`) to create a null-sink virtual speaker and capture its
monitor source. This only works on Linux with PulseAudio/PipeWire.

By migrating to `soundcard`, we gain cross-platform system audio capture:
- **Linux**: PulseAudio monitor sources (via CFFI)
- **macOS**: CoreAudio loopback devices
- **Windows**: WASAPI loopback endpoints

## Architecture

### AudioSource Protocol (unchanged)

```python
@runtime_checkable
class AudioSource(Protocol):
    sample_rate: int
    channels: int
    def start(self, callback: Callable[[bytes], None]) -> None: ...
    def stop(self) -> None: ...
    @property
    def is_capturing(self) -> bool: ...
```

No changes to the protocol itself — the new `SoundcardSource` implements the
same interface so `PipelineScheduler` and `LiveTranslatorApp` wiring remain
compatible.

### SoundcardSource (`live_translator/audio/soundcard_source.py`)

#### Initialization

```python
class SoundcardSource:
    def __init__(
        self,
        device_name: str | None = None,   # None = auto-select default loopback
        sample_rate: int = 16000,
        channels: int = 1,                # output always mono
        blocksize: int = 2048,
    ) -> None
```

- `device_name=None`: auto-select the default speaker's loopback (monitor)
- `device_name=<str>`: fuzzy-match against available loopback devices
- `sample_rate`: capture sample rate (soundcard will resample as needed)
- `channels`: output channel count (always 1 for mono PCM16)
- `blocksize`: internal capture buffer size

#### Lifecycle

**`start(callback)`**:
1. Let `sc = __import__('soundcard')` (lazy, top-level at module)
2. Call `sc.all_microphones(include_loopback=True)` to list all input devices
   including loopback monitors.
3. Select target device:
   - If `device_name` is set: `sc.get_microphone(device_name, include_loopback=True)`
   - If `device_name` is None: filter for `mic.isloopback`, prefer the default
     speaker's monitor by matching against `sc.default_speaker().name`
4. Fallback: if no loopback found, use `sc.default_microphone()` (log a warning)
5. Open the target as a `Recorder` context manager:
   `mic.recorder(samplerate=self.sample_rate, channels=self.channels, blocksize=self.blocksize)`
6. Start a daemon reader thread that loops:
   - Calls `recorder.record(numframes=None)` for low-latency chunks
   - Converts float32 numpy array → PCM16 int16 → bytes
   - Calls `callback(pcm16_bytes)`

**`stop()`**:
1. Signal stop event
2. Exit the recorder context manager (triggers cleanup)
3. Wait for reader thread

**`is_capturing`**:
- Returns boolean flag set by `start()`/`stop()`

#### Format Conversion

`soundcard` always returns `float32` numpy arrays (range [-1.0, 1.0]).

```python
import numpy as np

def _float32_to_pcm16(samples: np.ndarray) -> bytes:
    """Convert float32 [-1,1] to PCM16 int16 bytes."""
    # Clip to [-1, 1]
    samples = np.clip(samples, -1.0, 1.0)
    # Scale to int16 range
    pcm16 = (samples * 32767).astype(np.int16)
    return pcm16.tobytes()
```

#### Multi-channel → Mono Downmix

If the loopback device has multiple channels but we request mono output:
- `soundcard` handles channel mixing if `channels=-1` (mono mix on Linux)
- Otherwise, average all channels: `samples.mean(axis=1, keepdims=False)`

### Error Handling

| Scenario | Behaviour |
|---|---|
| `soundcard` not installed / import fails | `RuntimeError` on `start()` |
| No loopback device available | Fallback to default mic, logged as warning |
| Device disconnected during capture | Reader thread exits, `is_capturing` set to `False`, logged as error |
| `start()` called while already capturing | No-op (log warning) |
| `stop()` called while not capturing | No-op (log debug) |

## Files Changed

### New Files
- `live_translator/audio/soundcard_source.py` — SoundcardSource class

### Deleted Files
- `live_translator/audio/virtual_speaker.py` — replaced entirely
- `tests/test_audio/test_virtual_speaker.py` — replaced

### Modified Files
- `live_translator/audio/__init__.py` — export SoundcardSource, remove VirtualSpeakerSource
- `live_translator/gui/main_window.py`:
  - Replace `populate_sink_selector()` → `populate_loopback_devices()`
  - Replace "Output Device" label → "Audio Capture Device"
  - Use `SoundcardSource.list_devices()` instead of `VirtualSpeakerSource.list_sinks()`
  - Remove `_btn_refresh_sinks` (device list refreshed on open)
- `live_translator/gui/app.py`:
  - `_rebuild_pipeline()`: use `SoundcardSource` instead of `VirtualSpeakerSource`
  - Remove `populate_sink_selector()` call → use `populate_loopback_devices()`
- `live_translator/config/manager.py`:
  - Replace `audio.virtual_speaker` → `audio.capture` with new defaults
- `pyproject.toml`:
  - Add `soundcard>=0.4.6` to dependencies
  - Remove `sounddevice>=0.5.5` (was unused / no longer needed)

### New Test Files
- `tests/test_audio/test_soundcard_source.py` — unit tests for SoundcardSource

### Modified Test Files
- `tests/test_gui/test_output_device.py` — update for new GUI device selection

## GUI Changes

### Before (VirtualSpeakerSource)
```
┌─────────────────────────────────┐
│ Output Device: [▾ alsa_output.…]│ [↻]
└─────────────────────────────────┘
```

### After (SoundcardSource)
```
┌─────────────────────────────────┐
│ Capture Device: [▾ Built-in An…]│
└─────────────────────────────────┘
```

- Dropdown lists `soundcard` loopback devices (`isloopback=True`) plus real
  microphones as secondary fallback options.
- Each entry: `{name} ({channels}ch, {isloopback and "Loopback" or "Mic"})`
- No refresh button — list is fetched once at startup.

## Config Changes

```python
# Before
DEFAULT_CONFIG = {
    "audio": {
        "sample_rate": 16000,
        "channels": 1,
        "virtual_speaker": {
            "sink_name": "LiveTranslatorVirtualSpeaker",
            "sink_description": "LiveTranslator Virtual Speaker",
            "output_sink": "",
        },
    },
}

# After
DEFAULT_CONFIG = {
    "audio": {
        "sample_rate": 16000,
        "channels": 1,
        "capture": {
            "device_name": "",  # empty = auto
        },
    },
}
```

## Migration Path

No migration needed from user perspective — the config file is regenerated with
new defaults on next launch (old `virtual_speaker` keys are silently dropped by
the deep-merge logic).

## Out of Scope

- Audio playback/output routing (the virtual speaker's loopback-to-physical-sink
  feature is no longer needed — system audio plays through normal speakers)
- Recording to file
- Audio processing / VAD
