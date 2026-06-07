# LiteLLM Translation Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new `LiteLLMTranslateService` implementing the `Translator` Protocol, using LiteLLM SDK to route translation requests to 100+ LLM models.

**Architecture:** New `litellm_translate.py` service file following the same pattern as `deepl_translate.py`. Registered alongside DeepL in the service registry. Replaces the old `gpt` placeholder in config defaults.

**Tech Stack:** LiteLLM Python SDK (`>=1.60`), Python 3.12, pytest

---

### Task 1: Add litellm dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add litellm to dependencies**

Edit `pyproject.toml` to add `"litellm>=1.60"` to the `dependencies` list:

```toml
dependencies = [
    "numpy>=2.4.6",
    "pyside6>=6.11.1",
    "requests>=2.34.2",
    "sounddevice>=0.5.5",
    "websockets>=16.0",
    "litellm>=1.60",
]
```

- [ ] **Step 2: Install the dependency**

Run:
```bash
cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv add litellm 2>&1
```

Expected: `litellm` added to `pyproject.toml` and installed in `.venv`.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add litellm dependency"
```

---

### Task 2: Write failing tests

**Files:**
- Create: `tests/test_services/test_litellm_translate.py`

- [ ] **Step 1: Create the test file**

Create `tests/test_services/test_litellm_translate.py`:

```python
"""Tests for LiteLLM translator service."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from live_translator.services.litellm_translate import LiteLLMTranslateService


def test_service_identity() -> None:
    """Service should expose correct identity attributes."""
    service = LiteLLMTranslateService()
    assert service.service_id == "litellm"
    assert service.display_name == "LiteLLM (多模型)"


def test_default_config() -> None:
    """Default config should include expected fields."""
    service = LiteLLMTranslateService()
    assert "model" in service.config
    assert "api_key" in service.config
    assert "api_base" in service.config
    assert "max_tokens" in service.config
    assert "temperature" in service.config
    assert "system_prompt" in service.config
    assert service.config["model"] == "gpt-4o-mini"
    assert service.config["max_tokens"] == 1024
    assert service.config["temperature"] == 0.3


def test_translate_raises_without_model() -> None:
    """translate() should raise RuntimeError when model is empty."""
    service = LiteLLMTranslateService({"model": "", "api_key": "test"})
    with pytest.raises(RuntimeError, match="LiteLLM model not configured"):
        service.translate("Hello", "auto", "Chinese")


def test_translate_success() -> None:
    """translate() should call litellm.completion and return translated text."""
    service = LiteLLMTranslateService(
        {"model": "gpt-4o-mini", "api_key": "test-key"}
    )
    with patch("litellm.completion") as mock_completion:
        mock_completion.return_value.choices = [
            type("Choice", (), {"message": type("Msg", (), {"content": "你好"})})()
        ]
        result = service.translate("Hello", "auto", "Chinese")
    assert result == "你好"
    mock_completion.assert_called_once()
    call_kwargs = mock_completion.call_args.kwargs
    assert call_kwargs["model"] == "gpt-4o-mini"
    assert "Hello" in call_kwargs["messages"][1]["content"]


def test_translate_custom_prompt() -> None:
    """translate() should use custom system_prompt if provided."""
    service = LiteLLMTranslateService(
        {
            "model": "gpt-4o-mini",
            "api_key": "test-key",
            "system_prompt": "Translate to {target_lang}: {text}",
        }
    )
    with patch("litellm.completion") as mock_completion:
        mock_completion.return_value.choices = [
            type("Choice", (), {"message": type("Msg", (), {"content": "你好"})})()
        ]
        service.translate("Hello", "auto", "Chinese")
    messages = mock_completion.call_args.kwargs["messages"]
    assert messages[0]["content"] == "Translate to Chinese: Hello"


def test_translate_passes_optional_params() -> None:
    """translate() should pass api_base, max_tokens, temperature to litellm."""
    service = LiteLLMTranslateService(
        {
            "model": "gpt-4o-mini",
            "api_key": "test-key",
            "api_base": "https://custom.endpoint",
            "max_tokens": 512,
            "temperature": 0.7,
        }
    )
    with patch("litellm.completion") as mock_completion:
        mock_completion.return_value.choices = [
            type("Choice", (), {"message": type("Msg", (), {"content": "你好"})})()
        ]
        service.translate("Hello", "auto", "Chinese")
    kwargs = mock_completion.call_args.kwargs
    assert kwargs.get("api_base") == "https://custom.endpoint"
    assert kwargs.get("max_tokens") == 512
    assert kwargs.get("temperature") == 0.7


def test_translate_partial_returns_none() -> None:
    """translate_partial() should return None (sync mode)."""
    service = LiteLLMTranslateService()
    result = service.translate_partial("Hello", "auto", "Chinese")
    assert result is None


def test_supported_languages() -> None:
    """supported_languages() should return list of dicts with code/name."""
    service = LiteLLMTranslateService()
    langs = service.supported_languages()
    assert isinstance(langs, list)
    assert len(langs) > 3
    for lang in langs:
        assert "code" in lang
        assert "name" in lang
    codes = [l["code"] for l in langs]
    assert "ZH" in codes
    assert "EN" in codes
    assert "custom" in codes


def test_config_schema() -> None:
    """config_schema() should return valid JSON Schema."""
    schema = LiteLLMTranslateService.config_schema()
    assert schema["type"] == "object"
    assert "model" in schema["properties"]
    assert "api_key" in schema["properties"]
    assert "api_base" in schema["properties"]
    assert "max_tokens" in schema["properties"]
    assert "temperature" in schema["properties"]
    assert "system_prompt" in schema["properties"]
    assert schema["properties"]["api_key"]["format"] == "password"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd /home/ink/Desktop/develop/LiveTranslator && uv run pytest tests/test_services/test_litellm_translate.py -v 2>&1
```

Expected: All tests FAIL with `ModuleNotFoundError: No module named 'live_translator.services.litellm_translate'`.

---

### Task 3: Implement LiteLLMTranslateService

**Files:**
- Create: `live_translator/services/litellm_translate.py`

- [ ] **Step 1: Create the service file**

Create `live_translator/services/litellm_translate.py`:

```python
"""LiteLLM-based translation service supporting 100+ LLM models."""

from __future__ import annotations

from typing import Any


class LiteLLMTranslateService:
    """Translator implementation using LiteLLM SDK.

    Supports any model supported by LiteLLM (OpenAI, Anthropic, Google,
    open-source, custom endpoints, etc.). LiteLLM automatically routes
    to the correct API format based on the model name.
    """

    service_id = "litellm"
    display_name = "LiteLLM (多模型)"

    DEFAULT_SYSTEM_PROMPT = (
        "You are a professional translator. Translate the following text "
        "from {source_lang} to {target_lang}. "
        "Return ONLY the translated text, no explanations, no notes.\n\n"
        "Text: {text}"
    )

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize LiteLLM service.

        Args:
            config: Optional config dict. Defaults to empty config.
        """
        self.config = config or {
            "model": "gpt-4o-mini",
            "api_key": "",
            "api_base": "",
            "max_tokens": 1024,
            "temperature": 0.3,
            "system_prompt": "",
        }

    def translate(
        self, text: str, source_lang: str = "auto", target_lang: str | None = None
    ) -> str:
        """Translate text via LiteLLM completion.

        Args:
            text: Text to translate.
            source_lang: Source language code or name (``"auto"`` for detection).
            target_lang: Target language code or name.

        Returns:
            Translated text.

        Raises:
            RuntimeError: If model is not configured or API call fails.
        """
        model = self.config.get("model", "")
        if not model:
            raise RuntimeError("LiteLLM model not configured")

        target = target_lang or self.config.get("target_lang", "Chinese")

        # Build the prompt
        system_prompt = self.config.get("system_prompt", "")
        if system_prompt:
            user_content = system_prompt.format(
                source_lang=source_lang if source_lang != "auto" else "auto-detected",
                target_lang=target,
                text=text,
            )
            messages: list[dict[str, str]] = [
                {"role": "user", "content": user_content},
            ]
        else:
            messages = [
                {
                    "role": "system",
                    "content": (
                        f"You are a professional translator. Translate the following text "
                        f"from {source_lang if source_lang != 'auto' else 'auto-detected'} "
                        f"to {target}. "
                        f"Return ONLY the translated text, no explanations, no notes."
                    ),
                },
                {"role": "user", "content": text},
            ]

        import litellm

        litellm.suppress_debug_info = True
        litellm.drop_params = True

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        api_key = self.config.get("api_key", "")
        if api_key:
            kwargs["api_key"] = api_key

        api_base = self.config.get("api_base", "")
        if api_base:
            kwargs["api_base"] = api_base

        max_tokens = self.config.get("max_tokens")
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        temperature = self.config.get("temperature")
        if temperature is not None:
            kwargs["temperature"] = temperature

        try:
            response = litellm.completion(**kwargs)
            return str(response.choices[0].message.content)
        except Exception as exc:
            raise RuntimeError(f"LiteLLM translation failed: {exc}") from exc

    def translate_partial(
        self, text: str, source_lang: str = "auto", target_lang: str | None = None
    ) -> str | None:
        """Translate partial/in-progress text.

        In synchronous mode, partial results are not translated.
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

        LiteLLM supports natural language names, so this provides
        common options plus a ``"custom"`` entry for free-form input.

        Returns:
            A list of language dicts.
        """
        return [
            {"code": "ZH", "name": "Chinese"},
            {"code": "EN", "name": "English"},
            {"code": "JA", "name": "Japanese"},
            {"code": "KO", "name": "Korean"},
            {"code": "FR", "name": "French"},
            {"code": "DE", "name": "German"},
            {"code": "ES", "name": "Spanish"},
            {"code": "RU", "name": "Russian"},
            {"code": "PT", "name": "Portuguese"},
            {"code": "IT", "name": "Italian"},
            {"code": "AR", "name": "Arabic"},
            {"code": "custom", "name": "Custom..."},
        ]

    @classmethod
    def config_schema(cls) -> dict[str, Any]:
        """Return JSON Schema for LiteLLM configuration.

        Returns:
            JSON Schema dict with model, api_key, api_base, max_tokens,
            temperature, and system_prompt fields.
        """
        return {
            "type": "object",
            "title": "LiteLLM Configuration",
            "description": "Supports 100+ models via LiteLLM. Set model name and API key.",
            "properties": {
                "model": {
                    "type": "string",
                    "title": "Model",
                    "description": (
                        "Model identifier (e.g. gpt-4o-mini, claude-3-haiku, "
                        "gemini/gemini-2.0-flash, ollama/llama3)"
                    ),
                    "default": "gpt-4o-mini",
                },
                "api_key": {
                    "type": "string",
                    "title": "API Key",
                    "description": "API key for the model provider",
                    "format": "password",
                },
                "api_base": {
                    "type": "string",
                    "title": "API Base URL",
                    "description": (
                        "Custom API endpoint (optional). "
                        "E.g. https://api.openai.com/v1"
                    ),
                },
                "max_tokens": {
                    "type": "integer",
                    "title": "Max Tokens",
                    "description": "Maximum tokens in the response",
                    "default": 1024,
                    "minimum": 1,
                    "maximum": 128000,
                },
                "temperature": {
                    "type": "number",
                    "title": "Temperature",
                    "description": "Sampling temperature (0.0-2.0)",
                    "default": 0.3,
                    "minimum": 0.0,
                    "maximum": 2.0,
                },
                "system_prompt": {
                    "type": "string",
                    "title": "Custom Prompt (optional)",
                    "description": (
                        "Custom translation prompt template. "
                        "Use {source_lang}, {target_lang}, {text} as placeholders. "
                        "Leave empty for default."
                    ),
                    "format": "textarea",
                },
            },
            "required": ["model"],
        }
```

- [ ] **Step 2: Run tests to verify they pass**

Run:
```bash
cd /home/ink/Desktop/develop/LiveTranslator && uv run pytest tests/test_services/test_litellm_translate.py -v 2>&1
```

Expected: All 8 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add live_translator/services/litellm_translate.py tests/test_services/test_litellm_translate.py
git commit -m "feat: add LiteLLM translation service"
```

---

### Task 4: Update config defaults and wire into app

**Files:**
- Modify: `live_translator/config/manager.py`
- Modify: `live_translator/gui/app.py`

- [ ] **Step 1: Update DEFAULT_CONFIG in config/manager.py**

Replace the `gpt` provider block under `services.translator.providers` with `litellm`:

```python
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
            "active": "litellm",
            "providers": {
                "deepl": {
                    "api_key": "",
                    "target_lang": "ZH",
                },
                "litellm": {
                    "model": "gpt-4o-mini",
                    "api_key": "",
                    "api_base": "",
                    "max_tokens": 1024,
                    "temperature": 0.3,
                    "system_prompt": "",
                },
            },
        },
    },
    # ... rest unchanged ...
}
```

- [ ] **Step 2: Register the service in app.py**

In `live_translator/gui/app.py`, in `register_default_services()`, add the import and registration after the DeepL registration:

Edit around line 43-44 to add:
```python
from live_translator.services.litellm_translate import LiteLLMTranslateService
```

Edit after the DeepL registration (around line 59) to add:
```python
self._registry.register(
    "translator",
    LiteLLMTranslateService(
        config=self._config.get_service_config("translator", "litellm"),
    ),
)
```

- [ ] **Step 3: Verify all existing tests still pass**

Run:
```bash
cd /home/ink/Desktop/develop/LiveTranslator && uv run pytest -v 2>&1
```

Expected: All tests PASS (existing + new).

- [ ] **Step 4: Commit**

```bash
git add live_translator/config/manager.py live_translator/gui/app.py
git commit -m "feat: wire LiteLLM service into config defaults and app registration"
```

---

### Task 5: Verify functional check

- [ ] **Step 1: Run ruff lint check**

```bash
cd /home/ink/Desktop/develop/LiveTranslator && uv run ruff check live_translator/services/litellm_translate.py tests/test_services/test_litellm_translate.py 2>&1
```

Expected: No lint errors (or only pre-ignored violations).

- [ ] **Step 2: Run mypy type check**

```bash
cd /home/ink/Desktop/develop/LiveTranslator && uv run mypy live_translator/services/litellm_translate.py 2>&1
```

Expected: Success (no type errors).

- [ ] **Step 3: Final run-all-tests**

```bash
cd /home/ink/Desktop/develop/LiveTranslator && uv run pytest -v 2>&1
```

Expected: All tests PASS.
