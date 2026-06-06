# Qwen-ASR-Realtime Service — Design Spec

## Overview

Add a streaming ASR service using Alibaba Cloud Qwen-ASR-Realtime API via
WebSocket direct connection (low-level protocol), following the same
architecture as the existing `OpenAIRealtimeService`.

## Files

| File | Purpose |
|------|---------|
| `live_translator/services/qwen_asr.py` | Service + Session implementation |
| `tests/test_services/test_qwen_asr.py` | Unit tests |
| `docs/qwen_asr_realtime_reference.md` | API reference (already exists) |

## Architecture

### Class: `_QwenASRSession`

Implements the `ASRSession` protocol (`send_audio`, `poll`, `close`, `is_alive`,
`on_partial`, `on_final`, `on_error`).

**Constructor receives:**
- `api_key: str`
- `model: str`
- `session_config: dict` — language, sample_rate, input_audio_format, VAD params

**`_connect()` — lazy connection on first `send_audio()`:**
1. Open WebSocket to `wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model=<model>`
2. Set `Authorization: Bearer <api_key>` as additional header
3. Send `session.update` with configured language, VAD, audio format
4. Set `_connected = True`

**`send_audio(chunk)`:**
1. If not connected, call `_connect()`
2. Base64-encode PCM chunk
3. Send `{"type": "input_audio_buffer.append", "audio": b64data}`

**`poll()` — non-blocking message read (called from QTimer):**
1. Try `ws.recv(timeout=0.001)`
2. Parse JSON and dispatch by type:
   - `session.created` / `session.updated` → log, no callback
   - `conversation.item.input_audio_transcription.text` → `on_partial(text + stash)`
   - `conversation.item.input_audio_transcription.completed` → `on_final(transcript)`
   - `input_audio_buffer.speech_started` / `speech_stopped` → log (informational)
   - `error` → `on_error(RuntimeError(msg))`
   - `session.finished` → log (client should disconnect next)
3. Ignore `TimeoutError`, propagate other exceptions via `on_error`

**`close()`:**
1. Send `{"type": "session.finish", "event_id": "..."}`
2. Close WebSocket

### Class: `QwenASRService`

Implements `SpeechRecognizer` protocol (`service_id`, `display_name`,
`config_schema`, `create_session`).

| Attribute | Value |
|-----------|-------|
| `service_id` | `"qwen_asr"` |
| `display_name` | `"Qwen ASR Realtime"` |

**`config_schema()` returns:**

```json
{
  "type": "object",
  "title": "Qwen ASR Realtime Configuration",
  "properties": {
    "api_key": {
      "type": "string",
      "title": "API Key",
      "description": "Your Alibaba Cloud DashScope API key",
      "format": "password"
    },
    "model": {
      "type": "string",
      "title": "Model",
      "description": "ASR model ID",
      "default": "qwen3-asr-flash-realtime",
      "enum": ["qwen3-asr-flash-realtime"]
    },
    "language": {
      "type": "string",
      "title": "Language",
      "description": "Audio language code",
      "default": "zh",
      "enum": ["zh", "yue", "en", "ja", "de", "ko", "ru", "fr", "pt"]
    },
    "sample_rate": {
      "type": "integer",
      "title": "Sample Rate",
      "default": 16000,
      "enum": [8000, 16000]
    },
    "input_audio_format": {
      "type": "string",
      "title": "Audio Format",
      "default": "pcm",
      "enum": ["pcm", "opus"]
    }
  },
  "required": ["api_key"]
}
```

### WebSocket Event Flow

```
Client                               Server
  |                                    |
  |--- [WS Handshake] Authorization -->|  (401 if invalid key)
  |                                    |--- session.created
  |--- session.update ----------------|-
  |                                    |--- session.updated
  |--- input_audio_buffer.append -----|->  (continuous PCM stream)
  |                                    |--- input_audio_buffer.speech_started
  |                                    |--- conversation.item.input_audio_transcription.text (high freq)
  |                                    |--- conversation.item.input_audio_transcription.completed
  |                                    |--- input_audio_buffer.speech_stopped
  |                                    |
  |--- session.finish ----------------|-
  |                                    |--- session.finished
  |--- close() -----------------------|-
```

### Error Handling

- **No API key**: `create_session()` raises `RuntimeError("Qwen API key not configured")`
- **Invalid API key**: WebSocket handshake returns 401 → `websockets` raises exception → `on_error`
- **Network disconnect**: `recv()` raises exception → `on_error`
- **Server error event**: JSON `{"type": "error", ...}` → `on_error(RuntimeError(msg))`

### VAD Configuration

Default VAD parameters (configurable via session_config):
- `threshold`: 0.0 (recommended for general use)
- `silence_duration_ms`: 400 (fast response)

Set `turn_detection` to null for Manual mode (not used in initial release).

### Registration

In `app.py:register_default_services()`:

```python
from live_translator.services.qwen_asr import QwenASRService

qwen_asr_config = self._config.get_service_config("asr", "qwen_asr")
self._registry.register("asr", QwenASRService(qwen_asr_config))
```

### Testing

| Test | Description |
|------|-------------|
| `test_qwen_asr_config_schema` | Verify schema structure, types, defaults |
| `test_qwen_asr_service_identity` | Verify `service_id`, `display_name`, `config` |
| `test_qwen_asr_create_session_no_key` | Empty API key raises `RuntimeError` |
| `test_qwen_asr_session_poll_events` | Mock WebSocket, verify partial/final dispatch |

VAD parameters are passed via `session_config` dict; the reference doc already
exists at `docs/qwen_asr_realtime_reference.md`.

## Non-Goals

- Manual (push-to-talk) mode — not needed for continuous capture
- Emotion detection — not consumed by current pipeline
- Region selection (Singapore endpoint) — can be added later via config
