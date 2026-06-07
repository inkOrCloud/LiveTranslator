# LiveTranslator — 同声传译实时语音翻译

**LiveTranslator** is a real-time simultaneous interpretation application that captures system audio, performs speech recognition via cloud ASR services, and translates the transcribed text into your target language — displayed in a floating overlay window.

## Features

- 🎤 **System Audio Capture** — Captures audio from any running application using a PulseAudio virtual speaker (null-sink + `parec`), with optional loopback to physical speakers so you can still hear the original audio.
- 🗣️ **Streaming ASR** — Real-time speech recognition via:
  - **OpenAI Realtime API** (GPT-4o Realtime with Whisper transcription)
  - **Qwen ASR Realtime** (Alibaba Cloud DashScope, based on Qwen3)
- 🌐 **Translation** — Translate recognized speech into your target language via:
  - **DeepL API** — High-quality neural machine translation
  - **LiteLLM** — 100+ LLM models (OpenAI, Anthropic, Google, open-source, etc.)
- 🖥️ **Floating Overlay** — A frameless, always-on-top, translucent overlay window showing real-time ASR partial results and translation history. Supports drag-to-move and auto-maintains 1:2 aspect ratio.
- 🎛️ **Control Panel** — Main window with service selection, configuration forms, language selection, and pipeline controls (start/pause/stop).
- 🔄 **Configurable Pipeline** — Dynamically switch between ASR and translation providers at runtime.
- ⚙️ **JSON-Based Configuration** — All settings persisted to `~/.config/live-translator/config.json` with dot-notation access and JSON Schema-driven config forms.

## Architecture

```
System Audio (any app)
        │
        ▼
┌───────────────────┐
│ VirtualSpeaker     │  PulseAudio null-sink + parec
│ Source             │
└────────┬──────────┘
         │ PCM16 mono audio chunks (16kHz)
         ▼
┌───────────────────┐
│ PipelineScheduler  │  Orchestrates audio → ASR → translation
└────────┬──────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌──────────┐
│ ASR     │ │ Translator│
│ Service │ │ Service   │
└────┬───┘ └─────┬────┘
     │           │
     ▼           ▼
┌──────────────────────┐
│ TranslationOverlay    │  Floating overlay window
│ Window               │  (history + partial ASR)
└──────────────────────┘
```

## Dependencies

### Runtime Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| [PySide6](https://pypi.org/project/PySide6/) | >=6.11.1 | Qt6 GUI framework (main window, overlay, tray icon) |
| [sounddevice](https://pypi.org/project/sounddevice/) | >=0.5.5 | Audio capture (microphone source) |
| [numpy](https://pypi.org/project/numpy/) | >=2.4.6 | Audio data processing |
| [requests](https://pypi.org/project/requests/) | >=2.34.2 | HTTP client (DeepL API) |
| [websockets](https://pypi.org/project/websockets/) | >=16.0 | WebSocket client (OpenAI Realtime API, Qwen ASR) |
| [litellm](https://pypi.org/project/litellm/) | >=1.87.1 | Multi-model LLM proxy (100+ models) |

### System Dependencies

- **Python >= 3.12**
- **PulseAudio or PipeWire** (with PulseAudio compatibility)
- **`pactl`** and **`parec`** command-line tools (from `pulseaudio-utils` / `pipewire-audio`)

### Dev Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| [ruff](https://pypi.org/project/ruff/) | >=0.11.0 | Python linter and formatter |
| [mypy](https://pypi.org/project/mypy/) | >=1.15.0 | Static type checker |
| [pytest](https://pypi.org/project/pytest/) | >=9.0.3 | Testing framework |

## Installation

### 1. Install system dependencies

```bash
# Debian / Ubuntu
sudo apt install pulseaudio pulseaudio-utils python3.12 python3.12-venv

# Fedora
sudo dnf install pulseaudio pulseaudio-utils python3.12

# Arch Linux
sudo pacman -S pulseaudio pulseaudio-utils python

# For PipeWire users
sudo apt install pipewire-audio pipewire-pulse
```

### 2. Clone and set up

```bash
git clone https://github.com/your-username/LiveTranslator.git
cd LiveTranslator

# Create virtual environment and install dependencies
uv venv
uv sync
```

> The project uses [uv](https://docs.astral.sh/uv/) for dependency management. Install it with `curl -LsSf https://astral.sh/uv/install.sh | sh`.

### 3. Configure

Create `~/.config/live-translator/config.json`:

```json
{
  "services": {
    "asr": {
      "active": "openai_realtime",
      "providers": {
        "openai_realtime": {
          "api_key": "sk-...",
          "model": "gpt-4o-realtime-preview"
        },
        "qwen_asr": {
          "api_key": "sk-...",
          "model": "qwen3-asr-flash-realtime",
          "language": "zh"
        }
      }
    },
    "translator": {
      "active": "litellm",
      "providers": {
        "deepl": {
          "api_key": "...",
          "target_lang": "ZH"
        },
        "litellm": {
          "model": "gpt-4o-mini",
          "api_key": "sk-...",
          "api_base": "",
          "max_tokens": 1024,
          "temperature": 0.3
        }
      }
    }
  }
}
```

### 4. Run

```bash
uv run python main.py
```

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LIVETRANSLATOR_CONFIG` | `~/.config/live-translator/config.json` | Config file path |
| `LIVETRANSLATOR_LOG_LEVEL` | `INFO` | Log level (DEBUG/INFO/WARNING/ERROR) |
| `LIVETRANSLATOR_LOG_FILE` | *(none)* | Optional log file path (with rotation) |

## Usage

1. Launch the application — the control panel window appears.
2. Select an **ASR service** (OpenAI Realtime or Qwen ASR) and configure its API key.
3. Select a **Translation service** (DeepL or LiteLLM) and configure accordingly.
4. (Optional) Select an **output sink** if you want to hear audio through your speakers.
5. Click **Start** — the pipeline begins capturing system audio and streaming it through ASR → translation.
6. The **floating overlay window** shows real-time partial ASR results and translation history.
7. Use **Pause** / **Stop** to control the pipeline.
8. The application minimizes to the **system tray** — use the tray icon to show/hide windows.

## Project Structure

```
LiveTranslator/
├── main.py                                  # Application entry point
├── pyproject.toml                           # Project config & dependencies
├── live_translator/
│   ├── audio/
│   │   ├── source.py                        # AudioSource protocol
│   │   └── virtual_speaker.py               # PulseAudio virtual speaker capture
│   ├── config/
│   │   ├── manager.py                       # JSON config manager (dot-notation)
│   │   └── __init__.py
│   ├── gui/
│   │   ├── app.py                           # Application wiring & event loop
│   │   ├── main_window.py                   # Control panel window
│   │   ├── config_form.py                   # JSON Schema driven config form builder
│   │   ├── translation_overlay.py           # Floating subtitle overlay window
│   │   └── tray_icon.py                     # System tray icon
│   ├── pipeline/
│   │   ├── scheduler.py                     # Audio → ASR → translation pipeline
│   │   └── events.py                        # Pipeline status enum
│   ├── services/
│   │   ├── asr.py                           # ASRSession & SpeechRecognizer protocols
│   │   ├── translator.py                    # Translator protocol
│   │   ├── registry.py                      # Pluggable service registry
│   │   ├── openai_realtime.py               # OpenAI Realtime API ASR
│   │   ├── qwen_asr.py                      # Qwen ASR Realtime (Alibaba Cloud)
│   │   ├── deepl_translate.py               # DeepL API translation
│   │   └── litellm_translate.py             # LiteLLM multi-model translation
│   └── __init__.py
└── tests/
    ├── test_audio/
    ├── test_config/
    ├── test_gui/
    ├── test_pipeline/
    ├── test_services/
    └── __init__.py
```

## Running Tests

```bash
uv run pytest -v
```

The test suite covers:
- ASR service implementations (OpenAI Realtime, Qwen ASR)
- Translation services (DeepL, LiteLLM)
- Pipeline scheduler orchestration
- Config manager (load/save/merge)
- GUI components (config forms, overlay window, tray icon, main window)

## Code Quality

```bash
# Linting
uv run ruff check .

# Type checking
uv run mypy live_translator/

# Formatting
uv run ruff format . --check
```

## License

This project is licensed under the **GNU General Public License v3.0** — see the [LICENSE](LICENSE) file for details.
