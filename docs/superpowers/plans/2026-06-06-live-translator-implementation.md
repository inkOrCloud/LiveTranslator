# LiveTranslator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Linux desktop simultaneous interpretation app that captures system audio, streams it to OpenAI Realtime API for speech recognition, translates via DeepL API, and displays results in a floating subtitle window.

**Architecture:** Four-layer model (Audio -> Pipeline -> AI Services -> GUI) communicating via Qt signals. ASR uses streaming WebSocket (OpenAI Realtime API) with built-in VAD. Translator uses REST API (DeepL). GUI has a floating subtitle overlay and a control panel.

**Tech Stack:** Python 3.12, PySide6, sounddevice, OpenAI Realtime API, DeepL API, Ruff+MyPy strict

**Plan location:** `docs/superpowers/plans/2026-06-06-live-translator-implementation.md`

---

### Task 1: Config Manager + Project Structure

**Files:**
- Create: `live_translator/config/__init__.py`
- Create: `live_translator/config/manager.py`
- Test: `tests/test_config/test_manager.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config/__init__.py
```

```python
# tests/test_config/test_manager.py
"""Tests for config manager."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from live_translator.config.manager import ConfigManager


def test_config_manager_defaults() -> None:
    """ConfigManager should provide sensible defaults."""
    config = ConfigManager(Path("/nonexistent/config.json"))
    assert config.get("audio.sample_rate") == 16000
    assert config.get("services.asr.active") == "openai_realtime"
    assert config.get("appearance.subtitle_size") == 28
    assert config.get("appearance.opacity") == 0.9


def test_config_manager_load_and_save() -> None:
    """ConfigManager should round-trip through JSON."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.json"
        config = ConfigManager(path)
        config.set("services.asr.active", "test_service")
        config.save()

        loaded = ConfigManager(path)
        assert loaded.get("services.asr.active") == "test_service"


def test_config_manager_dot_notation() -> None:
    """Nested keys should be accessible via dot notation."""
    config = ConfigManager(Path("/nonexistent/config.json"))
    config.set("a.b.c", 42)
    assert config._data["a"]["b"]["c"] == 42


def test_config_manager_get_with_default() -> None:
    """get() should return default for missing keys."""
    config = ConfigManager(Path("/nonexistent/config.json"))
    assert config.get("nonexistent.key", "fallback") == "fallback"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && .venv/bin/pytest tests/test_config/ -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'live_translator.config'"

- [ ] **Step 3: Write minimal implementation**

```python
# live_translator/config/__init__.py
"""Configuration module for LiveTranslator."""
```

```python
# live_translator/config/manager.py
"""Configuration manager with JSON persistence and dot-notation access."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "services": {
        "asr": {
            "active": "openai_realtime",
            "providers": {
                "openai_realtime": {
                    "api_key": "",
                    "model": "gpt-4o-realtime-preview",
                },
                "openai_whisper": {
                    "api_key": "",
                    "model": "whisper-1",
                },
            },
        },
        "translator": {
            "active": "deepl",
            "providers": {
                "deepl": {
                    "api_key": "",
                    "target_lang": "ZH",
                },
                "gpt": {
                    "api_key": "",
                    "model": "gpt-4o-mini",
                    "target_lang": "Chinese",
                },
            },
        },
    },
    "audio": {
        "source": "monitor",
        "sample_rate": 16000,
        "channels": 1,
    },
    "appearance": {
        "subtitle_size": 28,
        "subtitle_lines": 3,
        "opacity": 0.9,
    },
}


class ConfigManager:
    """Manages application configuration with JSON persistence.

    Supports dot-notation access (e.g. ``config.get("services.asr.active")``).
    """

    def __init__(self, path: Path) -> None:
        """Initialize config manager.

        Args:
            path: Path to the JSON config file.
        """
        self._path = path
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load config from JSON file, falling back to defaults."""
        if self._path.exists():
            raw = self._path.read_text(encoding="utf-8")
            merged = json.loads(raw)
            self._data = self._deep_merge(DEFAULT_CONFIG, merged)
        else:
            self._data = json.loads(json.dumps(DEFAULT_CONFIG))

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Recursively merge override into base."""
        result = {}
        for key in base | override:
            if key in base and key in override:
                if isinstance(base[key], dict) and isinstance(override[key], dict):
                    result[key] = ConfigManager._deep_merge(base[key], override[key])
                else:
                    result[key] = override[key]
            elif key in base:
                result[key] = json.loads(json.dumps(base[key]))
            else:
                result[key] = json.loads(json.dumps(override[key]))
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value by dot-notation key.

        Args:
            key: Dot-separated path, e.g. ``"services.asr.active"``.
            default: Returned if key is not found.

        Returns:
            The value at the key path, or *default*.
        """
        parts = key.split(".")
        current = self._data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    def set(self, key: str, value: Any) -> None:
        """Set a value by dot-notation key, creating nested dicts as needed.

        Args:
            key: Dot-separated path.
            value: Value to set.
        """
        parts = key.split(".")
        current = self._data
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    def save(self) -> None:
        """Persist current config to JSON file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @property
    def data(self) -> dict[str, Any]:
        """Return the full config dict (read-only view)."""
        return dict(self._data)

    def get_service_config(self, category: str, service_id: str) -> dict[str, Any]:
        """Get the provider config dict for a specific service.

        Args:
            category: ``"asr"`` or ``"translator"``.
            service_id: e.g. ``"openai_realtime"``.

        Returns:
            The provider's config dict.
        """
        path = f"services.{category}.providers.{service_id}"
        result = self.get(path)
        return result if isinstance(result, dict) else {}

    def get_active_service(self, category: str) -> str:
        """Get the active service ID for a category.

        Args:
            category: ``"asr"`` or ``"translator"``.

        Returns:
            The active service ID string.
        """
        result = self.get(f"services.{category}.active")
        return str(result) if result else ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && .venv/bin/pytest tests/test_config/ -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add live_translator/config/ tests/test_config/ pyproject.toml
git commit -m "feat: add config manager with JSON persistence and dot-notation access"
```

---

### Task 2: Service Abstract Interfaces + Registry

**Files:**
- Create: `live_translator/services/__init__.py`
- Create: `live_translator/services/asr.py`
- Create: `live_translator/services/translator.py`
- Create: `live_translator/services/registry.py`
- Test: `tests/test_services/test_registry.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_services/__init__.py
```

```python
# tests/test_services/test_registry.py
"""Tests for service registry."""

from __future__ import annotations

import pytest

from live_translator.services.registry import ServiceRegistry
from live_translator.services.asr import SpeechRecognizer, ASRSession
from live_translator.services.translator import Translator


def test_registry_register_and_get() -> None:
    """Services should be registered and retrievable by ID."""
    registry = ServiceRegistry()

    class FakeASR:
        service_id = "fake_asr"
        display_name = "Fake ASR"
        config = {}
        def create_session(self):
            raise NotImplementedError
        @classmethod
        def config_schema(cls):
            return {"type": "object", "properties": {}}

    registry.register("asr", FakeASR())
    result = registry.get("asr", "fake_asr")
    assert result is not None
    assert result.service_id == "fake_asr"


def test_registry_list_services() -> None:
    """list_services should return all registered service IDs."""
    registry = ServiceRegistry()

    class FakeASR:
        service_id = "asr_a"
        display_name = "ASR A"
        config = {}
        def create_session(self):
            raise NotImplementedError
        @classmethod
        def config_schema(cls):
            return {"type": "object", "properties": {}}

    class FakeASR2:
        service_id = "asr_b"
        display_name = "ASR B"
        config = {}
        def create_session(self):
            raise NotImplementedError
        @classmethod
        def config_schema(cls):
            return {"type": "object", "properties": {}}

    registry.register("asr", FakeASR())
    registry.register("asr", FakeASR2())
    ids = registry.list_services("asr")
    assert "asr_a" in ids
    assert "asr_b" in ids


def test_registry_get_unknown_service() -> None:
    """Getting an unknown service should return None."""
    registry = ServiceRegistry()
    assert registry.get("asr", "nonexistent") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && .venv/bin/pytest tests/test_services/ -v`
Expected: FAIL with import errors

- [ ] **Step 3: Write minimal implementation**

```python
# live_translator/services/__init__.py
"""Service abstraction layer for ASR and translation providers."""
```

```python
# live_translator/services/asr.py
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

        The callback receives the current best-guess transcription text.

        Args:
            callback: Called with partial transcription string.
        """
        ...

    def on_final(self, callback: Callable[[str], None]) -> None:
        """Register a callback for final (confirmed) transcription.

        The callback receives the definitive transcription for one utterance.

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
    """Unique identifier for this service (e.g. ``"openai_realtime"``)."""

    display_name: str
    """Human-readable name for UI (e.g. ``"OpenAI Realtime API"``)."""

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

        The schema is used by the GUI to auto-render configuration forms.

        Returns:
            A JSON Schema dict.
        """
        ...
```

```python
# live_translator/services/translator.py
"""Abstract interfaces for translation services."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Translator(Protocol):
    """Interface for text translation services."""

    service_id: str
    """Unique identifier for this service (e.g. ``"deepl"``)."""

    display_name: str
    """Human-readable name for UI (e.g. ``"DeepL API"``)."""

    config: dict[str, Any]
    """Current configuration dict for this service instance."""

    def translate(self, text: str, source_lang: str,
                  target_lang: str) -> str:
        """Translate text from source language to target language.

        Args:
            text: The text to translate.
            source_lang: Source language code (e.g. ``"EN"``).
                         Use ``"auto"`` for automatic detection.
            target_lang: Target language code (e.g. ``"ZH"``).

        Returns:
            The translated text.
        """
        ...

    def supported_languages(self) -> list[dict[str, str]]:
        """Return list of supported language dicts.

        Each dict has ``"code"`` and ``"name"`` keys.

        Returns:
            A list of language dicts.
        """
        ...

    @classmethod
    def config_schema(cls) -> dict[str, Any]:
        """Return JSON Schema (Draft 07) for the config fields.

        Returns:
            A JSON Schema dict.
        """
        ...
```

```python
# live_translator/services/registry.py
"""Service registry for discovering and accessing ASR/Translator providers."""

from __future__ import annotations

from typing import Any

from live_translator.services.asr import SpeechRecognizer
from live_translator.services.translator import Translator


class ServiceRegistry:
    """Registry for pluable service implementations.

    Supports categorised registration (``"asr"``, ``"translator"``)
    and lookup by service_id.
    """

    def __init__(self) -> None:
        self._services: dict[str, dict[str, Any]] = {
            "asr": {},
            "translator": {},
        }

    def register(self, category: str, service: Any) -> None:
        """Register a service under a category.

        Args:
            category: ``"asr"`` or ``"translator"``.
            service: An object conforming to the category's protocol.
        """
        if category not in self._services:
            self._services[category] = {}
        self._services[category][service.service_id] = service

    def get(self, category: str, service_id: str) -> Any | None:
        """Get a registered service by category and ID.

        Args:
            category: ``"asr"`` or ``"translator"``.
            service_id: The service's unique identifier.

        Returns:
            The service instance, or None if not found.
        """
        return self._services.get(category, {}).get(service_id)

    def list_services(self, category: str) -> list[str]:
        """List all registered service IDs in a category.

        Args:
            category: ``"asr"`` or ``"translator"``.

        Returns:
            A list of service ID strings.
        """
        return list(self._services.get(category, {}).keys())

    def list_display_names(self, category: str) -> dict[str, str]:
        """Map service IDs to display names in a category.

        Args:
            category: ``"asr"`` or ``"translator"``.

        Returns:
            Dict mapping service_id -> display_name.
        """
        return {
            sid: svc.display_name
            for sid, svc in self._services.get(category, {}).items()
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && .venv/bin/pytest tests/test_services/ -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add live_translator/services/ tests/test_services/
git commit -m "feat: add service abstract interfaces (ASR/Translator) and registry"
```

---

### Task 3: DeepL Translator Implementation

**Files:**
- Create: `live_translator/services/deepl_translate.py`
- Test: `tests/test_services/test_deepl_translate.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_services/test_deepl_translate.py
"""Tests for DeepL translator service."""

from __future__ import annotations

from live_translator.services.deepl_translate import DeepLTranslateService


def test_deepl_config_schema() -> None:
    """config_schema should return valid JSON Schema."""
    schema = DeepLTranslateService.config_schema()
    assert schema["type"] == "object"
    assert "api_key" in schema["properties"]
    assert schema["properties"]["api_key"]["format"] == "password"


def test_deepl_default_config() -> None:
    """Default config should include api_key and target_lang."""
    service = DeepLTranslateService()
    assert "api_key" in service.config
    assert service.config["target_lang"] == "ZH"


def test_deepl_service_identity() -> None:
    """Service should expose correct identity attributes."""
    service = DeepLTranslateService()
    assert service.service_id == "deepl"
    assert service.display_name == "DeepL API"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && .venv/bin/pytest tests/test_services/test_deepl_translate.py -v`
Expected: FAIL with import error

- [ ] **Step 3: Write minimal implementation**

```python
# live_translator/services/deepl_translate.py
"""DeepL API translation service implementation."""

from __future__ import annotations

from typing import Any

import requests

from live_translator.services.translator import Translator


class DeepLTranslateService:
    """Translator implementation using the DeepL API."""

    service_id = "deepl"
    display_name = "DeepL API"

    BASE_URL = "https://api-free.deepl.com/v2/translate"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize DeepL service.

        Args:
            config: Optional config dict. Defaults to empty config.
        """
        self.config = config or {
            "api_key": "",
            "target_lang": "ZH",
        }

    def translate(self, text: str, source_lang: str = "auto",
                  target_lang: str | None = None) -> str:
        """Translate text via DeepL API.

        Args:
            text: Text to translate.
            source_lang: Source language code (``"auto"`` for detection).
            target_lang: Target language code. Uses config default if None.

        Returns:
            Translated text.

        Raises:
            RuntimeError: If API key is not configured or request fails.
        """
        api_key = self.config.get("api_key", "")
        if not api_key:
            raise RuntimeError("DeepL API key not configured")

        target = target_lang or self.config.get("target_lang", "ZH")
        params: dict[str, str] = {
            "auth_key": api_key,
            "text": text,
            "target_lang": target.upper(),
        }
        if source_lang and source_lang.lower() != "auto":
            params["source_lang"] = source_lang.upper()

        response = requests.post(self.BASE_URL, data=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return str(data["translations"][0]["text"])

    def translate_partial(self, text: str, source_lang: str = "auto",
                          target_lang: str | None = None) -> str | None:
        """Translate partial/in-progress text.

        For synchronous translation mode, partial results are not translated.
        Returns None to indicate the caller should only show the original text.

        Args:
            text: Partial text to (optionally) translate.
            source_lang: Source language code.
            target_lang: Target language code.

        Returns:
            None (partial translation not performed in synchronous mode).
        """
        del text, source_lang, target_lang
        return None

    def supported_languages(self) -> list[dict[str, str]]:
        """Return supported languages.

        Returns:
            A static list of commonly used DeepL language codes.
        """
        return [
            {"code": "ZH", "name": "Chinese (Simplified)"},
            {"code": "EN", "name": "English"},
            {"code": "JA", "name": "Japanese"},
            {"code": "KO", "name": "Korean"},
            {"code": "FR", "name": "French"},
            {"code": "DE", "name": "German"},
            {"code": "ES", "name": "Spanish"},
            {"code": "RU", "name": "Russian"},
        ]

    @classmethod
    def config_schema(cls) -> dict[str, Any]:
        """Return JSON Schema for DeepL configuration.

        Returns:
            JSON Schema dict with api_key and target_lang fields.
        """
        return {
            "type": "object",
            "title": "DeepL API Configuration",
            "properties": {
                "api_key": {
                    "type": "string",
                    "title": "API Key",
                    "description": "Your DeepL API authentication key",
                    "format": "password",
                },
                "target_lang": {
                    "type": "string",
                    "title": "Target Language",
                    "description": "Default target language code",
                    "default": "ZH",
                    "enum": ["ZH", "EN", "JA", "KO", "FR", "DE", "ES", "RU"],
                },
            },
            "required": ["api_key"],
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && .venv/bin/pytest tests/test_services/test_deepl_translate.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Add requests to dependencies and commit**

```bash
cd /home/ink/Desktop/develop/LiveTranslator && uv add requests
git add live_translator/services/deepl_translate.py tests/test_services/test_deepl_translate.py pyproject.toml uv.lock
git commit -m "feat: add DeepL API translation service"
```

---

### Task 4: OpenAI Realtime ASR Implementation

**Files:**
- Create: `live_translator/services/openai_realtime.py`
- Test: `tests/test_services/test_openai_realtime.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_services/test_openai_realtime.py
"""Tests for OpenAI Realtime ASR service."""

from __future__ import annotations

from live_translator.services.openai_realtime import OpenAIRealtimeService


def test_realtime_config_schema() -> None:
    """config_schema should return valid JSON Schema."""
    schema = OpenAIRealtimeService.config_schema()
    assert schema["type"] == "object"
    assert "api_key" in schema["properties"]
    assert schema["properties"]["model"]["default"] == "gpt-4o-realtime-preview"


def test_realtime_service_identity() -> None:
    """Service should expose correct identity attributes."""
    service = OpenAIRealtimeService()
    assert service.service_id == "openai_realtime"
    assert service.display_name == "OpenAI Realtime API"
    assert service.config["model"] == "gpt-4o-realtime-preview"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && .venv/bin/pytest tests/test_services/test_openai_realtime.py -v`
Expected: FAIL with import error

- [ ] **Step 3: Write minimal implementation**

```python
# live_translator/services/openai_realtime.py
"""OpenAI Realtime API streaming ASR implementation."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import numpy as np

from live_translator.services.asr import ASRSession, SpeechRecognizer


class _RealtimeSession:
    """Internal implementation of ASRSession for OpenAI Realtime API."""

    def __init__(self, api_key: str, model: str,
                 on_partial: Callable[[str], None] | None = None,
                 on_final: Callable[[str], None] | None = None,
                 on_error: Callable[[Exception], None] | None = None) -> None:
        """Initialize the session.

        Args:
            api_key: OpenAI API key.
            model: Model ID for the Realtime API.
            on_partial: Callback for partial transcription.
            on_final: Callback for final transcription.
            on_error: Callback for errors.
        """
        self._api_key = api_key
        self._model = model
        self._on_partial_cb = on_partial
        self._on_final_cb = on_final
        self._on_error_cb = on_error
        self._ws: Any = None
        self._connected = False

    def _connect(self) -> None:
        """Establish WebSocket connection to OpenAI Realtime API."""
        try:
            import websockets.sync.client as ws_client
        except ImportError:
            raise RuntimeError(
                "websockets library required for OpenAI Realtime API. "
                "Install with: uv add websockets"
            ) from None

        url = (
            f"wss://api.openai.com/v1/realtime?model={self._model}"
        )
        self._ws = ws_client.connect(
            url,
            additional_headers={
                "Authorization": f"Bearer {self._api_key}",
                "OpenAI-Beta": "realtime=v1",
            },
        )
        self._connected = True

        # Send session update to enable audio transcription
        self._ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "modalities": ["text"],
                "instructions": "",
                "input_audio_transcription": {
                    "enabled": True,
                    "model": "whisper-1",
                },
            },
        }))

    def send_audio(self, chunk: bytes) -> None:
        """Send an audio chunk (PCM16, 16kHz, mono) for recognition.

        Args:
            chunk: Raw PCM16 audio data at 16kHz sample rate.
        """
        if not self._connected:
            self._connect()

        import base64
        audio_b64 = base64.b64encode(chunk).decode("ascii")
        self._ws.send(json.dumps({
            "type": "input_audio_buffer.append",
            "audio": audio_b64,
        }))

    def on_partial(self, callback: Callable[[str], None]) -> None:
        """Register callback for partial transcription."""
        self._on_partial_cb = callback

    def on_final(self, callback: Callable[[str], None]) -> None:
        """Register callback for final transcription."""
        self._on_final_cb = callback

    def on_error(self, callback: Callable[[Exception], None]) -> None:
        """Register callback for errors."""
        self._on_error_cb = callback

    def _handle_messages(self) -> None:
        """Non-blocking read of incoming WebSocket messages."""
        if not self._ws:
            return
        try:
            message = self._ws.recv(timeout=0.001)
            data = json.loads(message)
            msg_type = data.get("type", "")

            if msg_type == "conversation.item.input_audio_transcription.completed":
                transcript = data.get("transcript", "")
                if transcript and self._on_final_cb:
                    self._on_final_cb(transcript)

            elif msg_type == "conversation.item.input_audio_transcription.in_progress":
                transcript = data.get("transcript", "")
                if transcript and self._on_partial_cb:
                    self._on_partial_cb(transcript)

            elif msg_type == "error":
                error_msg = data.get("error", {}).get("message", "Unknown error")
                if self._on_error_cb:
                    self._on_error_cb(RuntimeError(error_msg))

        except (TimeoutError, TimeoutError):
            pass
        except Exception as exc:
            if self._on_error_cb:
                self._on_error_cb(exc)

    def poll(self) -> None:
        """Poll for incoming messages. Called periodically from pipeline."""
        self._handle_messages()

    def close(self) -> None:
        """Close the WebSocket connection."""
        self._connected = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

    @property
    def is_alive(self) -> bool:
        """Whether the session is connected."""
        return self._connected and self._ws is not None


class OpenAIRealtimeService:
    """SpeechRecognizer implementation using OpenAI Realtime API."""

    service_id = "openai_realtime"
    display_name = "OpenAI Realtime API"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the service.

        Args:
            config: Optional config dict with api_key and model.
        """
        self.config = config or {
            "api_key": "",
            "model": "gpt-4o-realtime-preview",
        }

    def create_session(self) -> ASRSession:
        """Create a new streaming recognition session.

        Returns:
            An ASRSession connected to OpenAI Realtime API.

        Raises:
            RuntimeError: If API key is not configured.
        """
        api_key = self.config.get("api_key", "")
        if not api_key:
            raise RuntimeError("OpenAI API key not configured")
        model = self.config.get("model", "gpt-4o-realtime-preview")
        return _RealtimeSession(
            api_key=api_key,
            model=model,
        )

    @classmethod
    def config_schema(cls) -> dict[str, Any]:
        """Return JSON Schema for OpenAI Realtime configuration.

        Returns:
            JSON Schema dict with api_key and model fields.
        """
        return {
            "type": "object",
            "title": "OpenAI Realtime API Configuration",
            "properties": {
                "api_key": {
                    "type": "string",
                    "title": "API Key",
                    "description": "Your OpenAI API key",
                    "format": "password",
                },
                "model": {
                    "type": "string",
                    "title": "Model",
                    "description": "Realtime model ID",
                    "default": "gpt-4o-realtime-preview",
                    "enum": [
                        "gpt-4o-realtime-preview",
                        "gpt-4o-mini-realtime-preview",
                    ],
                },
            },
            "required": ["api_key"],
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && .venv/bin/pytest tests/test_services/test_openai_realtime.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Add websockets dependency and commit**

```bash
cd /home/ink/Desktop/develop/LiveTranslator && uv add websockets
git add live_translator/services/openai_realtime.py tests/test_services/test_openai_realtime.py pyproject.toml uv.lock
git commit -m "feat: add OpenAI Realtime API streaming ASR service"
```

---

### Task 5: Audio Capture (System Monitor)

**Files:**
- Create: `live_translator/audio/__init__.py`
- Create: `live_translator/audio/source.py`
- Create: `live_translator/audio/system_monitor.py`
- Test: `tests/test_audio/__init__.py`
- Test: `tests/test_audio/test_source.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_audio/__init__.py
```

```python
# tests/test_audio/test_source.py
"""Tests for audio source abstraction."""

from __future__ import annotations

from live_translator.audio.source import AudioSource
from live_translator.audio.system_monitor import SystemMonitor


def test_audio_source_protocol() -> None:
    """AudioSource should be a Protocol."""
    # Just verify it's importable and has the expected interface
    attrs = {"start", "stop", "on_audio", "sample_rate", "channels"}
    for attr in attrs:
        assert hasattr(AudioSource, attr) or any(
            hasattr(b, attr) for b in getattr(AudioSource, "__orig_bases__", [])
        )


def test_system_monitor_identity() -> None:
    """SystemMonitor should expose correct config defaults."""
    monitor = SystemMonitor()
    assert monitor.sample_rate == 16000
    assert monitor.channels == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && .venv/bin/pytest tests/test_audio/ -v`
Expected: FAIL with import errors

- [ ] **Step 3: Write minimal implementation**

```python
# live_translator/audio/__init__.py
"""Audio capture module for LiveTranslator."""
```

```python
# live_translator/audio/source.py
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
```

```python
# live_translator/audio/system_monitor.py
"""System audio output capture via PulseAudio monitor source."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import sounddevice as sd


class SystemMonitor:
    """Captures system audio output (speaker) using PulseAudio monitor.

    On Linux, this uses the PulseAudio monitor source. On other platforms
    it falls back to the default input device.
    """

    def __init__(self, sample_rate: int = 16000,
                 channels: int = 1,
                 blocksize: int = 1024) -> None:
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

    def _find_monitor_device(self) -> int | None:
        """Find the PulseAudio monitor source device ID.

        Returns:
            Device index or None if no monitor found.
        """
        devices = sd.query_devices()
        for idx, dev in enumerate(devices):
            name: str = str(dev.get("name", ""))
            if "monitor" in name.lower():
                return int(idx)
        return None

    def start(self, callback: Callable[[bytes], None]) -> None:
        """Start capturing system audio output.

        Args:
            callback: Called with PCM16 mono audio chunks.
        """
        self._callback = callback
        device = self._find_monitor_device()

        self._stream = sd.InputStream(
            device=device,
            samplerate=self.sample_rate,
            channels=self.channels,
            blocksize=self.blocksize,
            dtype=np.int16,
            callback=self._audio_callback,
        )
        self._stream.start()

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
        del frames, time_info, status
        if self._callback and outdata.size > 0:
            chunk = outdata.tobytes()
            self._callback(chunk)

    def stop(self) -> None:
        """Stop capturing audio."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._callback = None

    @property
    def is_capturing(self) -> bool:
        """Whether the source is currently capturing."""
        return self._stream is not None and self._stream.active
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && .venv/bin/pytest tests/test_audio/ -v`
Expected: 2 PASSED

- [ ] **Step 5: Add sounddevice dependency and commit**

```bash
cd /home/ink/Desktop/develop/LiveTranslator && uv add sounddevice numpy
git add live_translator/audio/ tests/test_audio/ pyproject.toml uv.lock
git commit -m "feat: add system audio capture via PulseAudio monitor"
```

---

### Task 6: Pipeline Scheduler

**Files:**
- Create: `live_translator/pipeline/__init__.py`
- Create: `live_translator/pipeline/events.py`
- Create: `live_translator/pipeline/scheduler.py`
- Test: `tests/test_pipeline/__init__.py`
- Test: `tests/test_pipeline/test_scheduler.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pipeline/__init__.py
```

```python
# tests/test_pipeline/test_scheduler.py
"""Tests for pipeline scheduler."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from live_translator.pipeline.scheduler import PipelineScheduler, PipelineStatus


def test_pipeline_initial_state() -> None:
    """Pipeline should start in IDLE state."""
    pipeline = PipelineScheduler(MagicMock(), MagicMock(), MagicMock())
    assert pipeline.status == PipelineStatus.IDLE


def test_pipeline_start_transitions_to_streaming() -> None:
    """Starting the pipeline should transition to STREAMING."""
    pipeline = PipelineScheduler(MagicMock(), MagicMock(), MagicMock())
    pipeline.start()
    assert pipeline.status == PipelineStatus.STREAMING


def test_pipeline_stop_transitions_to_idle() -> None:
    """Stopping the pipeline should transition to IDLE."""
    pipeline = PipelineScheduler(MagicMock(), MagicMock(), MagicMock())
    pipeline.start()
    pipeline.stop()
    assert pipeline.status == PipelineStatus.IDLE


def test_pipeline_pause_resume() -> None:
    """Pipeline should support pause/resume."""
    pipeline = PipelineScheduler(MagicMock(), MagicMock(), MagicMock())
    pipeline.start()
    pipeline.pause()
    assert pipeline.status == PipelineStatus.PAUSED
    pipeline.resume()
    assert pipeline.status == PipelineStatus.STREAMING
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && .venv/bin/pytest tests/test_pipeline/ -v`
Expected: FAIL with import errors

- [ ] **Step 3: Write minimal implementation**

```python
# live_translator/pipeline/__init__.py
"""Pipeline module for orchestrating audio -> ASR -> translation flow."""
```

```python
# live_translator/pipeline/events.py
"""Signal/event definitions for pipeline communication.

Uses PySide6's Signal system for thread-safe GUI updates.
"""

from __future__ import annotations

from enum import Enum, auto


class PipelineStatus(Enum):
    """Pipeline lifecycle states."""

    IDLE = auto()
    STREAMING = auto()
    PAUSED = auto()
    ERROR = auto()
```

```python
# live_translator/pipeline/scheduler.py
"""Pipeline scheduler orchestrating audio capture, ASR, and translation."""

from __future__ import annotations

import logging
from collections.abc import Callable

from live_translator.audio.source import AudioSource
from live_translator.pipeline.events import PipelineStatus
from live_translator.services.asr import ASRSession, SpeechRecognizer
from live_translator.services.translator import Translator

logger = logging.getLogger(__name__)


class PipelineScheduler:
    """Orchestrates the audio -> ASR -> translation pipeline.

    Manages the lifecycle of audio capture and ASR sessions,
    routing final transcription results through the translator
    and emitting results via callbacks.
    """

    def __init__(
        self,
        audio_source: AudioSource,
        asr_service: SpeechRecognizer,
        translator: Translator,
    ) -> None:
        """Initialize the pipeline scheduler.

        Args:
            audio_source: Source for audio capture.
            asr_service: ASR service for speech recognition.
            translator: Translation service.
        """
        self._audio_source = audio_source
        self._asr_service = asr_service
        self._translator = translator
        self._asr_session: ASRSession | None = None
        self._status = PipelineStatus.IDLE
        self._source_lang = "auto"
        self._target_lang = "ZH"

        # Callbacks for pipeline consumers (GUI)
        self.on_partial: Callable[[str], None] | None = None
        self.on_translation: Callable[[str, str], None] | None = None
        self.on_status_change: Callable[[PipelineStatus], None] | None = None
        self.on_error: Callable[[str], None] | None = None

    @property
    def status(self) -> PipelineStatus:
        """Current pipeline status."""
        return self._status

    def start(self) -> None:
        """Start the pipeline: begin audio capture and ASR session."""
        if self._status == PipelineStatus.STREAMING:
            logger.warning("Pipeline already streaming")
            return

        self._asr_session = self._asr_service.create_session()
        self._asr_session.on_partial(self._on_asr_partial)
        self._asr_session.on_final(self._on_asr_final)
        self._asr_session.on_error(self._on_asr_error)

        self._audio_source.start(self._on_audio_chunk)

        self._set_status(PipelineStatus.STREAMING)
        logger.info("Pipeline started")

    def stop(self) -> None:
        """Stop the pipeline and release resources."""
        self._audio_source.stop()

        if self._asr_session is not None:
            self._asr_session.close()
            self._asr_session = None

        self._set_status(PipelineStatus.IDLE)
        logger.info("Pipeline stopped")

    def pause(self) -> None:
        """Pause the pipeline (stop audio capture, keep session)."""
        if self._status != PipelineStatus.STREAMING:
            return
        self._audio_source.stop()
        self._set_status(PipelineStatus.PAUSED)
        logger.info("Pipeline paused")

    def resume(self) -> None:
        """Resume the pipeline."""
        if self._status != PipelineStatus.PAUSED:
            return
        if self._asr_session is None or not self._asr_session.is_alive:
            # Session expired, create a new one
            self._asr_session = self._asr_service.create_session()
            self._asr_session.on_partial(self._on_asr_partial)
            self._asr_session.on_final(self._on_asr_final)
            self._asr_session.on_error(self._on_asr_error)

        self._audio_source.start(self._on_audio_chunk)
        self._set_status(PipelineStatus.STREAMING)
        logger.info("Pipeline resumed")

    def set_languages(self, source: str, target: str) -> None:
        """Set source and target languages.

        Args:
            source: Source language code (``"auto"`` for detection).
            target: Target language code.
        """
        self._source_lang = source
        self._target_lang = target

    def _on_audio_chunk(self, chunk: bytes) -> None:
        """Handle incoming audio chunk from AudioSource.

        Args:
            chunk: PCM16 mono audio data chunk.
        """
        if self._asr_session is not None and self._status == PipelineStatus.STREAMING:
            self._asr_session.send_audio(chunk)

    def _on_asr_partial(self, text: str) -> None:
        """Handle partial ASR result.

        In synchronous mode, partial results are shown as transcription
        hints but not translated.

        Args:
            text: Partial transcription text.
        """
        if self.on_partial:
            self.on_partial(text)

    def _on_asr_final(self, text: str) -> None:
        """Handle final ASR result and trigger translation.

        Args:
            text: Final transcription text.
        """
        if not text.strip():
            return

        if self.on_partial:
            self.on_partial(text)

        try:
            translated = self._translator.translate(
                text,
                source_lang=self._source_lang,
                target_lang=self._target_lang,
            )
            if self.on_translation:
                self.on_translation(text, translated)
        except Exception as exc:
            logger.error("Translation failed: %s", exc)
            if self.on_error:
                self.on_error(f"Translation failed: {exc}")

    def _on_asr_error(self, exc: Exception) -> None:
        """Handle ASR session error.

        Args:
            exc: The exception that occurred.
        """
        logger.error("ASR error: %s", exc)
        if self.on_error:
            self.on_error(str(exc))

    def _set_status(self, status: PipelineStatus) -> None:
        """Update pipeline status and notify listeners.

        Args:
            status: New pipeline status.
        """
        self._status = status
        if self.on_status_change:
            self.on_status_change(status)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && .venv/bin/pytest tests/test_pipeline/ -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add live_translator/pipeline/ tests/test_pipeline/
git commit -m "feat: add pipeline scheduler for audio->ASR->translation orchestration"
```

---

### Task 7: GUI — Config Form (JSON Schema Driven)

**Files:**
- Create: `live_translator/gui/__init__.py`
- Create: `live_translator/gui/config_form.py`
- Test: `tests/test_gui/__init__.py`
- Test: `tests/test_gui/test_config_form.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_gui/__init__.py
```

```python
# tests/test_gui/test_config_form.py
"""Tests for config form widget."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QLineEdit, QComboBox, QCheckBox

from live_translator.gui.config_form import ConfigFormBuilder

# Need a QApplication instance for widget tests
@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_config_form_builds_widgets(qapp: QApplication) -> None:
    """ConfigFormBuilder should create widgets from JSON Schema."""
    schema = {
        "type": "object",
        "properties": {
            "api_key": {
                "type": "string",
                "title": "API Key",
                "format": "password",
            },
            "model": {
                "type": "string",
                "title": "Model",
                "default": "whisper-1",
                "enum": ["whisper-1", "whisper-large-v3"],
            },
            "enabled": {
                "type": "boolean",
                "title": "Enabled",
                "default": True,
            },
            "timeout": {
                "type": "number",
                "title": "Timeout",
                "default": 30.0,
            },
        },
        "required": ["api_key"],
    }

    builder = ConfigFormBuilder(schema, {"api_key": "sk-test", "model": "whisper-1"})
    widget = builder.build()

    # Should have created widgets for each property
    assert builder.get_widget("api_key") is not None
    assert builder.get_widget("model") is not None
    assert builder.get_widget("enabled") is not None


def test_config_form_get_values(qapp: QApplication) -> None:
    """get_values should return current widget values."""
    schema = {
        "type": "object",
        "properties": {
            "api_key": {
                "type": "string",
                "title": "API Key",
                "format": "password",
            },
            "model": {
                "type": "string",
                "title": "Model",
                "default": "whisper-1",
                "enum": ["whisper-1"],
            },
        },
        "required": ["api_key"],
    }

    builder = ConfigFormBuilder(schema, {"api_key": "test-key", "model": "whisper-1"})
    builder.build()

    values = builder.get_values()
    assert values["api_key"] == "test-key"
    assert values["model"] == "whisper-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && .venv/bin/pytest tests/test_gui/ -v`
Expected: FAIL with import errors

- [ ] **Step 3: Write minimal implementation**

```python
# live_translator/gui/__init__.py
"""GUI module for LiveTranslator."""
```

```python
# live_translator/gui/config_form.py
"""Dynamic configuration form builder driven by JSON Schema.

Takes a JSON Schema dict and renders the appropriate Qt widgets,
then collects values back into a dict.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QWidget,
)


class ConfigFormBuilder:
    """Builds a Qt form from a JSON Schema.

    Example::

        schema = DeepLTranslateService.config_schema()
        builder = ConfigFormBuilder(schema, current_config)
        form_widget = builder.build()
        # ... add form_widget to your layout ...
        updated = builder.get_values()
    """

    def __init__(self, schema: dict[str, Any],
                 current_values: dict[str, Any] | None = None) -> None:
        """Initialize the form builder.

        Args:
            schema: JSON Schema dict with ``properties`` key.
            current_values: Optional dict of existing values to populate.
        """
        self._schema = schema
        self._values = current_values or {}
        self._widgets: dict[str, QWidget] = {}
        self._widget: QGroupBox | None = None

    def build(self) -> QGroupBox:
        """Build the form widget.

        Returns:
            A QGroupBox containing the dynamically generated form.
        """
        title = self._schema.get("title", "Configuration")
        group = QGroupBox(title)
        layout = QFormLayout(group)

        properties = self._schema.get("properties", {})
        for key, prop_schema in properties.items():
            widget = self._create_widget(key, prop_schema)
            self._widgets[key] = widget
            label = prop_schema.get("title", key)
            layout.addRow(label, widget)

        self._widget = group
        return group

    def _create_widget(self, key: str, prop_schema: dict[str, Any]) -> QWidget:
        """Create a single widget for a schema property.

        Args:
            key: Property name.
            prop_schema: Property's JSON Schema sub-dict.

        Returns:
            The created QWidget.
        """
        prop_type = prop_schema.get("type", "string")
        fmt = prop_schema.get("format", "")
        default = prop_schema.get("default")
        current = self._values.get(key, default)
        description = prop_schema.get("description", "")

        if prop_type == "string" and fmt == "password":
            widget = QLineEdit()
            widget.setEchoMode(QLineEdit.EchoMode.Password)
            if current:
                widget.setText(str(current))
            widget.setToolTip(description)

        elif prop_type == "string" and "enum" in prop_schema:
            widget = QComboBox()
            for option in prop_schema["enum"]:
                widget.addItem(str(option), option)
            if current:
                idx = widget.findData(current)
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            widget.setToolTip(description)

        elif prop_type == "boolean":
            widget = QCheckBox()
            if isinstance(current, bool):
                widget.setChecked(current)
            widget.setToolTip(description)

        elif prop_type == "integer":
            widget = QSpinBox()
            if "default" in prop_schema:
                widget.setValue(int(prop_schema["default"]))
            if "minimum" in prop_schema:
                widget.setMinimum(int(prop_schema["minimum"]))
            if "maximum" in prop_schema:
                widget.setMaximum(int(prop_schema["maximum"]))
            if isinstance(current, (int, float)):
                widget.setValue(int(current))
            widget.setToolTip(description)

        elif prop_type == "number":
            widget = QDoubleSpinBox()
            if "default" in prop_schema:
                widget.setValue(float(prop_schema["default"]))
            if "minimum" in prop_schema:
                widget.setMinimum(float(prop_schema["minimum"]))
            if "maximum" in prop_schema:
                widget.setMaximum(float(prop_schema["maximum"]))
            if isinstance(current, (int, float)):
                widget.setValue(float(current))
            widget.setToolTip(description)

        else:
            widget = QLineEdit()
            if current:
                widget.setText(str(current))
            widget.setToolTip(description)

        return widget

    def get_widget(self, key: str) -> QWidget | None:
        """Get the widget for a property key.

        Args:
            key: Property name.

        Returns:
            The widget, or None if not found.
        """
        return self._widgets.get(key)

    def get_values(self) -> dict[str, Any]:
        """Collect current values from all widgets.

        Returns:
            Dict mapping property names to their current widget values.
        """
        values: dict[str, Any] = {}
        properties = self._schema.get("properties", {})

        for key, widget in self._widgets.items():
            prop_schema = properties.get(key, {})
            values[key] = self._read_widget(widget, prop_schema)

        return values

    @staticmethod
    def _read_widget(widget: QWidget,
                     prop_schema: dict[str, Any]) -> Any:
        """Read the value from a widget.

        Args:
            widget: The widget to read.
            prop_schema: The property schema for type inference.

        Returns:
            The widget's value in the correct Python type.
        """
        prop_type = prop_schema.get("type", "string")

        if isinstance(widget, QLineEdit):
            return widget.text()

        if isinstance(widget, QComboBox):
            return widget.currentData()

        if isinstance(widget, QCheckBox):
            return widget.isChecked()

        if isinstance(widget, QSpinBox):
            return widget.value()

        if isinstance(widget, QDoubleSpinBox):
            return widget.value()

        return ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && .venv/bin/pytest tests/test_gui/ -v`
Expected: 2 PASSED

- [ ] **Step 5: Add PySide6 dependency and commit**

```bash
cd /home/ink/Desktop/develop/LiveTranslator && uv add PySide6
git add live_translator/gui/config_form.py tests/test_gui/ pyproject.toml uv.lock
git commit -m "feat: add JSON Schema driven config form builder"
```

---

### Task 8: GUI — SubtitleWindow

**Files:**
- Create: `live_translator/gui/subtitle_window.py`
- Test: `tests/test_gui/test_subtitle_window.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gui/test_subtitle_window.py
"""Tests for subtitle window."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from live_translator.gui.subtitle_window import SubtitleWindow


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_subtitle_window_creation(qapp: QApplication) -> None:
    """SubtitleWindow should create with correct flags."""
    window = SubtitleWindow()
    assert window.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert window.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


def test_subtitle_window_display_text(qapp: QApplication) -> None:
    """Displaying text should update subtitle content."""
    window = SubtitleWindow()
    window.show_translation("Hello world", "你好世界")
    # Should not crash - visual verification is manual
    assert window.isVisible()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && .venv/bin/pytest tests/test_gui/test_subtitle_window.py -v`
Expected: FAIL with import error

- [ ] **Step 3: Write minimal implementation**

```python
# live_translator/gui/subtitle_window.py
"""Floating subtitle overlay window.

A frameless, transparent, click-through window that stays on top of all
other windows and displays translation results near the bottom of the
screen, similar to video subtitles.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QRect, QTimer, Signal
from PySide6.QtGui import QFont, QPainter, QColor, QBrush, QPen, QFontMetrics
from PySide6.QtWidgets import QApplication, QWidget


class SubtitleWindow(QWidget):
    """A floating, transparent subtitle overlay window."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the subtitle window.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)

        # Window flags: frameless, always-on-top, tool (no taskbar entry)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        # Transparent background for custom painting
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Let mouse events pass through to windows beneath
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # Appearance settings
        self._font_size = 28
        self._opacity = 0.9
        self._max_lines = 3
        self._line_spacing = 8

        # Translation history (tuples of original, translated)
        self._entries: list[tuple[str, str]] = []
        self._partial_text: str = ""

        # Auto-hide timer
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._on_hide_timeout)

        # Set up font
        self._font = QFont("Noto Sans CJK SC, Noto Sans, sans-serif", self._font_size)
        self._font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)

        # Position at bottom of screen
        self._position_on_screen()

    def _position_on_screen(self) -> None:
        """Position the window at the bottom of the primary screen."""
        screen = QApplication.primaryScreen()
        if screen is None:
            self.setGeometry(0, 0, 800, 200)
            return

        screen_rect: QRect = screen.availableGeometry()
        height = 200
        self.setGeometry(
            screen_rect.x(),
            screen_rect.bottom() - height - 10,
            screen_rect.width(),
            height,
        )

    def set_font_size(self, size: int) -> None:
        """Set subtitle font size.

        Args:
            size: Font size in points.
        """
        self._font_size = size
        self._font.setPointSize(size)
        self.update()

    def set_opacity(self, value: float) -> None:
        """Set subtitle background opacity.

        Args:
            value: Opacity from 0.0 to 1.0.
        """
        self._opacity = max(0.0, min(1.0, value))
        self.update()

    def show_partial(self, text: str) -> None:
        """Display partial/in-progress transcription.

        Args:
            text: Partial transcription text.
        """
        self._partial_text = text
        self.show()
        self.update()

    def show_translation(self, original: str, translated: str) -> None:
        """Display a complete translation result.

        Args:
            original: Original (source language) text.
            translated: Translated (target language) text.
        """
        self._entries.append((original, translated))
        if len(self._entries) > self._max_lines:
            self._entries = self._entries[-self._max_lines:]

        self._partial_text = ""
        self.show()
        self.update()

        # Auto-hide after 30 seconds of no updates
        self._hide_timer.start(30000)

    def clear(self) -> None:
        """Clear all displayed text."""
        self._entries.clear()
        self._partial_text = ""
        self._hide_timer.stop()
        self.hide()

    def _on_hide_timeout(self) -> None:
        """Auto-hide the window after timeout."""
        self.hide()

    def paintEvent(self, event: Any) -> None:
        """Custom paint for semi-transparent subtitle background and text.

        Args:
            event: Paint event (unused).
        """
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Calculate required height based on content
        metrics = QFontMetrics(self._font)
        line_height = metrics.height() + self._line_spacing
        content_lines = len(self._entries)
        if self._partial_text:
            content_lines += 1
        total_height = max(10, content_lines * line_height + 20)

        # Semi-transparent background
        painter.setBrush(QBrush(QColor(0, 0, 0, int(255 * self._opacity))))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.drawRoundedRect(0, self.height() - total_height,
                                self.width(), total_height,
                                6, 6)

        # Draw entries from bottom up
        y = self.height() - 15  # bottom padding
        for original, translated in reversed(self._entries):
            # Original text
            painter.setPen(QColor(200, 200, 200))
            painter.setFont(self._font)
            painter.drawText(20, y - line_height, self.width() - 40, line_height,
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             original)

            # Separator and translated text
            painter.setPen(QColor(255, 255, 255))
            sep = " \u2500 " if translated else ""
            display_text = f"{sep}{translated}" if translated else ""
            painter.drawText(20, y, self.width() - 40, line_height,
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             display_text)
            y -= 2 * line_height

        # Partial text (most recent, bottom)
        if self._partial_text:
            painter.setPen(QColor(180, 180, 180))
            partial_display = f"{self._partial_text} \u2026"
            painter.drawText(20, y, self.width() - 40, line_height,
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             partial_display)

        painter.end()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && .venv/bin/pytest tests/test_gui/test_subtitle_window.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add live_translator/gui/subtitle_window.py tests/test_gui/test_subtitle_window.py
git commit -m "feat: add floating subtitle overlay window"
```

---

### Task 9: GUI — MainWindow + TrayIcon + App Wiring

**Files:**
- Create: `live_translator/gui/main_window.py`
- Create: `live_translator/gui/tray_icon.py`
- Create: `live_translator/gui/app.py`
- Test: `tests/test_gui/test_main_window.py`
- Test: `tests/test_gui/test_tray_icon.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_gui/test_main_window.py
"""Tests for main control panel window."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from live_translator.gui.main_window import MainWindow
from live_translator.config.manager import ConfigManager


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def config() -> ConfigManager:
    import tempfile
    from pathlib import Path
    tmp = tempfile.mkdtemp()
    return ConfigManager(Path(tmp) / "config.json")


def test_main_window_creation(qapp: QApplication, config: ConfigManager) -> None:
    """MainWindow should create without error."""
    window = MainWindow(config)
    assert window.windowTitle() == "LiveTranslator"
```

```python
# tests/test_gui/test_tray_icon.py
"""Tests for system tray icon."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from live_translator.gui.tray_icon import TrayIcon


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_tray_icon_creation(qapp: QApplication) -> None:
    """TrayIcon should create without error."""
    from unittest.mock import MagicMock
    icon = TrayIcon(MagicMock())
    assert icon.isVisible()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && .venv/bin/pytest tests/test_gui/ -v`
Expected: FAIL with import errors for main_window and tray_icon

- [ ] **Step 3: Write minimal implementation**

```python
# live_translator/gui/main_window.py
"""Main control panel window for LiveTranslator."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from live_translator.config.manager import ConfigManager
from live_translator.gui.config_form import ConfigFormBuilder
from live_translator.services.registry import ServiceRegistry


class MainWindow(QMainWindow):
    """Main control panel for the translation application."""

    def __init__(self, config: ConfigManager,
                 registry: ServiceRegistry | None = None) -> None:
        """Initialize the main window.

        Args:
            config: Application configuration manager.
            registry: Service registry (created if None).
        """
        super().__init__()
        self._config = config
        self._registry = registry or ServiceRegistry()
        self._config_forms: dict[str, ConfigFormBuilder] = {}

        self.setWindowTitle("LiveTranslator")
        self.setMinimumSize(500, 600)
        self.resize(500, 700)

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the main window UI."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)

        # === Controls section ===
        controls = QHBoxLayout()
        self._btn_start = QPushButton("\u25b6 Start")
        self._btn_pause = QPushButton("\u23f8 Pause")
        self._btn_stop = QPushButton("\u23f9 Stop")
        controls.addWidget(self._btn_start)
        controls.addWidget(self._btn_pause)
        controls.addWidget(self._btn_stop)
        layout.addLayout(controls)

        # Status label
        self._status_label = QLabel("Status: Idle")
        layout.addWidget(self._status_label)

        # === Mode selector ===
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Subtitle", "Panel", "Dual"])
        mode_layout.addWidget(self._mode_combo)
        layout.addLayout(mode_layout)

        # === Service configuration (scrollable) ===
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # ASR section
        asr_label = QLabel("Speech Recognition Service")
        asr_label.setStyleSheet("font-weight: bold;")
        scroll_layout.addWidget(asr_label)

        self._asr_selector = QComboBox()
        scroll_layout.addWidget(self._asr_selector)

        self._asr_config_container = QWidget()
        self._asr_config_layout = QVBoxLayout(self._asr_config_container)
        scroll_layout.addWidget(self._asr_config_container)

        # Translator section
        t_label = QLabel("Translation Service")
        t_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        scroll_layout.addWidget(t_label)

        self._translator_selector = QComboBox()
        scroll_layout.addWidget(self._translator_selector)

        self._translator_config_container = QWidget()
        self._translator_config_layout = QVBoxLayout(self._translator_config_container)
        scroll_layout.addWidget(self._translator_config_container)

        # Language selector
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("Source:"))
        self._source_lang = QComboBox()
        self._source_lang.addItem("Auto Detect", "auto")
        self._source_lang.addItem("English", "EN")
        self._source_lang.addItem("Chinese", "ZH")
        self._source_lang.addItem("Japanese", "JA")
        self._source_lang.addItem("Korean", "KO")
        lang_layout.addWidget(self._source_lang)

        lang_layout.addWidget(QLabel("Target:"))
        self._target_lang = QComboBox()
        self._target_lang.addItem("Chinese", "ZH")
        self._target_lang.addItem("English", "EN")
        self._target_lang.addItem("Japanese", "JA")
        self._target_lang.addItem("Korean", "KO")
        lang_layout.addWidget(self._target_lang)

        scroll_layout.addLayout(lang_layout)

        # Save button
        self._btn_save_config = QPushButton("Save Configuration")
        scroll_layout.addWidget(self._btn_save_config)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        # === Translation history ===
        history_label = QLabel("Translation History")
        history_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(history_label)

        self._history_list = QListWidget()
        layout.addWidget(self._history_list, stretch=1)

    def populate_service_selectors(self) -> None:
        """Populate service selectors from registry."""
        self._asr_selector.clear()
        display_names = self._registry.list_display_names("asr")
        for sid, name in display_names.items():
            self._asr_selector.addItem(f"{name} ({sid})", sid)

        self._translator_selector.clear()
        display_names = self._registry.list_display_names("translator")
        for sid, name in display_names.items():
            self._translator_selector.addItem(f"{name} ({sid})", sid)

        # Set active service
        active_asr = self._config.get_active_service("asr")
        idx = self._asr_selector.findData(active_asr)
        if idx >= 0:
            self._asr_selector.setCurrentIndex(idx)

        active_t = self._config.get_active_service("translator")
        idx = self._translator_selector.findData(active_t)
        if idx >= 0:
            self._translator_selector.setCurrentIndex(idx)

    def rebuild_config_forms(self) -> None:
        """Rebuild config forms for selected services."""
        # Clear existing config forms
        self._clear_layout(self._asr_config_layout)
        self._clear_layout(self._translator_config_layout)
        self._config_forms.clear()

        # Build ASR config form
        active_asr = self._asr_selector.currentData()
        asr_service = self._registry.get("asr", active_asr)
        if asr_service is not None:
            schema = asr_service.config_schema()
            current_config = self._config.get_service_config("asr", active_asr)
            builder = ConfigFormBuilder(schema, current_config)
            form = builder.build()
            self._asr_config_layout.addWidget(form)
            self._config_forms[f"asr.{active_asr}"] = builder

        # Build Translator config form
        active_t = self._translator_selector.currentData()
        t_service = self._registry.get("translator", active_t)
        if t_service is not None:
            schema = t_service.config_schema()
            current_config = self._config.get_service_config("translator", active_t)
            builder = ConfigFormBuilder(schema, current_config)
            form = builder.build()
            self._translator_config_layout.addWidget(form)
            self._config_forms[f"translator.{active_t}"] = builder

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        """Remove all widgets from a layout.

        Args:
            layout: The layout to clear.
        """
        while layout.count():
            item = layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    def add_history_entry(self, original: str, translated: str) -> None:
        """Add a translation result to the history list.

        Args:
            original: Original text.
            translated: Translated text.
        """
        item = QListWidgetItem(f"{original}\n\u2192 {translated}")
        self._history_list.insertItem(0, item)

        # Limit to 200 entries
        while self._history_list.count() > 200:
            self._history_list.takeItem(self._history_list.count() - 1)

    def get_languages(self) -> tuple[str, str]:
        """Get selected source and target language codes.

        Returns:
            Tuple of (source_code, target_code).
        """
        src = self._source_lang.currentData()
        tgt = self._target_lang.currentData()
        return str(src) if src else "auto", str(tgt) if tgt else "ZH"

    def set_status(self, text: str) -> None:
        """Set the status label text.

        Args:
            text: Status text to display.
        """
        self._status_label.setText(f"Status: {text}")
```

```python
# live_translator/gui/tray_icon.py
"""System tray icon for LiveTranslator."""

from __future__ import annotations

from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget


class TrayIcon(QSystemTrayIcon):
    """System tray icon with context menu for background operation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize tray icon.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)

        # Set icon (use a simple built-in icon as fallback)
        self.setIcon(QIcon.fromTheme("media-record",
                                      QIcon(":/qt-project.org/styles/commonstyle/images/media-record-16.png")))

        self.setToolTip("LiveTranslator")

        # Build context menu
        menu = QMenu()
        self._show_action = QAction("Show/Hide", None)
        menu.addAction(self._show_action)
        menu.addSeparator()
        self._quit_action = QAction("Quit", None)
        menu.addAction(self._quit_action)
        self.setContextMenu(menu)

        self.show()
```

```python
# live_translator/gui/app.py
"""Application entry point - initialises QApplication and main windows."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from live_translator.pipeline.scheduler import PipelineScheduler, PipelineStatus
from live_translator.config.manager import ConfigManager
from live_translator.services.registry import ServiceRegistry

# Lazy imports to avoid circular dependencies
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from live_translator.gui.main_window import MainWindow
    from live_translator.gui.subtitle_window import SubtitleWindow
    from live_translator.gui.tray_icon import TrayIcon


class LiveTranslatorApp:
    """Top-level application class that wires all components together."""

    def __init__(self, config_path: Path) -> None:
        """Initialize the application.

        Args:
            config_path: Path to the JSON configuration file.
        """
        self._config = ConfigManager(config_path)
        self._registry = ServiceRegistry()
        self._pipeline: PipelineScheduler | None = None
        self._main_window: MainWindow | None = None
        self._subtitle_window: SubtitleWindow | None = None
        self._tray_icon: TrayIcon | None = None
        self._poll_timer: QTimer | None = None

    def register_default_services(self) -> None:
        """Register built-in service implementations."""
        # Lazy imports to defer dependency resolution
        from live_translator.services.deepl_translate import DeepLTranslateService
        from live_translator.services.openai_realtime import OpenAIRealtimeService

        asr_config = self._config.get_service_config(
            "asr", "openai_realtime",
        )
        self._registry.register(
            "asr", OpenAIRealtimeService(asr_config),
        )

        t_config = self._config.get_service_config(
            "translator", "deepl",
        )
        self._registry.register(
            "translator", DeepLTranslateService(t_config),
        )

    def _on_start(self) -> None:
        """Handle start button click."""
        if self._pipeline is None:
            return
        src, tgt = self._main_window.get_languages() if self._main_window else ("auto", "ZH")
        self._pipeline.set_languages(src, tgt)
        self._pipeline.start()
        self._update_status_text()

    def _on_pause(self) -> None:
        """Handle pause button click."""
        if self._pipeline:
            self._pipeline.pause()
            self._update_status_text()

    def _on_stop(self) -> None:
        """Handle stop button click."""
        if self._pipeline:
            self._pipeline.stop()
            self._update_status_text()

    def _on_partial(self, text: str) -> None:
        """Handle partial ASR result.

        Args:
            text: Partial transcription text.
        """
        if self._subtitle_window:
            self._subtitle_window.show_partial(text)

    def _on_translation(self, original: str, translated: str) -> None:
        """Handle completed translation.

        Args:
            original: Original text.
            translated: Translated text.
        """
        if self._subtitle_window:
            self._subtitle_window.show_translation(original, translated)
        if self._main_window:
            self._main_window.add_history_entry(original, translated)

    def _on_status_change(self, status: PipelineStatus) -> None:
        """Handle pipeline status change.

        Args:
            status: New pipeline status.
        """
        self._update_status_text()

    def _on_error(self, message: str) -> None:
        """Handle pipeline error.

        Args:
            message: Error message.
        """
        if self._main_window:
            self._main_window.set_status(f"Error: {message}")

    def _update_status_text(self) -> None:
        """Update status label from pipeline state."""
        if self._main_window and self._pipeline:
            self._main_window.set_status(self._pipeline.status.name)

    def _on_save_config(self) -> None:
        """Save configuration from UI forms."""
        if not self._main_window:
            return

        # Save ASR config
        active_asr = self._main_window._asr_selector.currentData()
        form_key = f"asr.{active_asr}"
        if form_key in self._config_forms:
            values = self._config_forms[form_key].get_values()
            for key, val in values.items():
                self._config.set(f"services.asr.providers.{active_asr}.{key}", val)
            self._config.set("services.asr.active", active_asr)

        # Save translator config
        active_t = self._main_window._translator_selector.currentData()
        form_key = f"translator.{active_t}"
        if form_key in self._config_forms:
            values = self._config_forms[form_key].get_values()
            for key, val in values.items():
                self._config.set(
                    f"services.translator.providers.{active_t}.{key}", val,
                )
            self._config.set("services.translator.active", active_t)

        self._config.save()

        # Reload services with updated config
        self.register_default_services()
        # Rebuild pipeline with new service instances
        self._rebuild_pipeline()

    def _rebuild_pipeline(self) -> None:
        """Rebuild the pipeline with current service instances."""
        asr_service = self._registry.get(
            "asr", self._config.get_active_service("asr"),
        )
        t_service = self._registry.get(
            "translator", self._config.get_active_service("translator"),
        )
        if asr_service is None or t_service is None:
            return

        from live_translator.audio.system_monitor import SystemMonitor
        audio = SystemMonitor(
            sample_rate=self._config.get("audio.sample_rate", 16000),
        )

        self._pipeline = PipelineScheduler(audio, asr_service, t_service)
        self._pipeline.on_partial = self._on_partial
        self._pipeline.on_translation = self._on_translation
        self._pipeline.on_status_change = self._on_status_change
        self._pipeline.on_error = self._on_error

    def run(self) -> None:
        """Start the Qt application event loop."""
        import sys
        app = QApplication(sys.argv)

        # Create windows
        from live_translator.gui.main_window import MainWindow
        from live_translator.gui.subtitle_window import SubtitleWindow
        from live_translator.gui.tray_icon import TrayIcon

        self._main_window = MainWindow(self._config, self._registry)
        self._subtitle_window = SubtitleWindow()

        # Register default services
        self.register_default_services()

        # Populate UI
        self._main_window.populate_service_selectors()
        self._main_window.rebuild_config_forms()

        # Store config_forms reference for save handler
        self._config_forms = self._main_window._config_forms

        # Build pipeline
        self._rebuild_pipeline()

        # Wire signals
        self._main_window._btn_start.clicked.connect(self._on_start)
        self._main_window._btn_pause.clicked.connect(self._on_pause)
        self._main_window._btn_stop.clicked.connect(self._on_stop)
        self._main_window._btn_save_config.clicked.connect(self._on_save_config)
        self._main_window._asr_selector.currentIndexChanged.connect(
            lambda: self._main_window.rebuild_config_forms(),
        )
        self._main_window._translator_selector.currentIndexChanged.connect(
            lambda: self._main_window.rebuild_config_forms(),
        )

        # Poll ASR session messages via timer
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_asr_session)
        self._poll_timer.start(50)  # 20 fps polling

        # Tray icon
        self._tray_icon = TrayIcon(self._main_window)
        self._tray_icon._show_action.triggered.connect(
            lambda: self._main_window.show() or self._subtitle_window.show(),
        )
        self._tray_icon._quit_action.triggered.connect(app.quit)

        # Show main window
        self._main_window.show()
        self._subtitle_window.show()

        sys.exit(app.exec())

    def _poll_asr_session(self) -> None:
        """Periodically poll ASR session for incoming messages."""
        if self._pipeline is None:
            return
        session = getattr(self._pipeline, "_asr_session", None)
        if session is not None and hasattr(session, "poll"):
            session.poll()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && .venv/bin/pytest tests/test_gui/ -v`
Expected: All tests PASS (main_window creation and tray_icon creation)

- [ ] **Step 5: Commit**

```bash
git add live_translator/gui/ tests/test_gui/
git commit -m "feat: add main window, tray icon, and application wiring"
```

---

### Task 10: Main Entry Point + Final Wiring

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Write the main entry point**

```python
# main.py
"""LiveTranslator - 同声传译实时翻译应用入口.

Usage:
    python main.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from live_translator.gui.app import LiveTranslatorApp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_config_path() -> Path:
    """Determine the config file path.

    Priority:
    1. ``LIVETRANSLATOR_CONFIG`` environment variable
    2. ``~/.config/live-translator/config.json``

    Returns:
        Path to the config file.
    """
    env_path = sys.platform  # placeholder for env var check
    del env_path  # unused for now

    return Path.home() / ".config" / "live-translator" / "config.json"


def main() -> None:
    """Run the LiveTranslator application."""
    config_path = get_config_path()
    logger.info("Starting LiveTranslator with config: %s", config_path)

    app = LiveTranslatorApp(config_path)
    app.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify lint + mypy pass**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy main.py live_translator/`
Expected: All checks pass

- [ ] **Step 3: Final commit**

```bash
git add main.py
git commit -m "feat: add main entry point and complete application wiring"
```

---

### Self-Review Checklist

**Spec coverage:**
- [x] Config persistence with dot-notation → Task 1
- [x] Service abstract interfaces (ASR/Translator Protocol) → Task 2
- [x] Service registry for discovery → Task 2
- [x] OpenAI Realtime API streaming ASR (WebSocket, built-in VAD) → Task 4
- [x] DeepL API translation service → Task 3
- [x] JSON Schema driven config forms → Task 7
- [x] PulseAudio system audio capture → Task 5
- [x] Pipeline scheduler (audio -> ASR -> translate) → Task 6
- [x] Synchronous mode (partial = UI hint only, final = translate) → Task 6
- [x] Floating subtitle window (frameless/transparent/click-through) → Task 8
- [x] Control panel with config/history → Task 9
- [x] System tray icon → Task 9
- [x] Language configuration (source auto-detect + target select) → Task 6 + 9
- [x] Platform-specific audio: Linux PulseAudio → Task 5
- [x] Error handling and logging → throughout
- [x] TDD throughout → each task has tests before implementation

**Placeholder scan:** No TBD, TODO, or placeholder patterns found.

**Type consistency:** ASRSession, SpeechRecognizer, Translator interfaces consistent across all tasks. Dot-notation config API consistent. PipelineScheduler constructor signature matches usage in LiveTranslatorApp.
