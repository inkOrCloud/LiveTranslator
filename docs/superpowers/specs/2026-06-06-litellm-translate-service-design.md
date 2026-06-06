# LiteLLM Translation Service Design

**Date:** 2026-06-06
**Status:** Draft
**Project:** LiveTranslator

## 1. Objective

Add a new `LiteLLMTranslateService` that uses the [LiteLLM](https://github.com/BerriAI/litellm) Python SDK (`litellm>=1.60`) to call 100+ LLM models (OpenAI, Claude, Gemini, open-source, custom endpoints, etc.) for text translation. LiteLLM automatically routes to the correct API format based on the model name.

## 2. Design Decisions

- **Approach**: New standalone service file (`litellm_translate.py`) implementing the existing `Translator` Protocol. Replaces the placeholder `gpt` translator provider in config.
- **Configuration fields exposed in UI**: `model` (string, required), `api_key` (password), `api_base` (string, optional, for custom endpoints), `max_tokens` (integer, default 1024), `temperature` (number, default 0.3), `system_prompt` (text, optional, for customising the translation prompt).
- **Language selection**: Retains the existing Source/Target language dropdowns. LiteLLM accepts natural language strings (e.g. `"Chinese"`, `"Japanese"`).
- **Partial translation**: Returns `None` — same behaviour as DeepL (synchronous mode, partial results shown as transcription only).

## 3. File Changes

### 3.1. New File: `live_translator/services/litellm_translate.py`

Implements `LiteLLMTranslateService` with:

- `service_id = "litellm"`
- `display_name = "LiteLLM (多模型)"`
- `translate(text, source_lang, target_lang)` — constructs a system prompt and calls `litellm.completion()` synchronously, returning only the translated text.
- `translate_partial(text, source_lang, target_lang)` — returns `None`.
- `supported_languages()` — returns a static list of common language codes plus a `"custom"` entry allowing users to type any language name.
- `config_schema()` — JSON Schema returning all configurable fields.

**Translation prompt (default):**

```
You are a professional translator. Translate the following text from {source_lang} to {target_lang}.
Return ONLY the translated text, no explanations, no notes.

Text: {text}
```

The user can override this via the `system_prompt` config field.

### 3.2. Modified: `live_translator/config/manager.py`

Update `DEFAULT_CONFIG`:

- Replace the `gpt` provider block under `services.translator.providers` with a `litellm` block.
- Update default model from `"gpt-4o-mini"` to `"gpt-4o-mini"` (kept the same but now routed through LiteLLM).

### 3.3. Modified: `live_translator/gui/app.py`

Add registration of `LiteLLMTranslateService` in `register_default_services()`.

### 3.4. Modified: `pyproject.toml`

Add `"litellm>=1.60"` to the `dependencies` list.

## 4. Default Config Structure

```json
{
  "services": {
    "translator": {
      "active": "litellm",
      "providers": {
        "deepl": { ... },
        "litellm": {
          "model": "gpt-4o-mini",
          "api_key": "",
          "api_base": "",
          "max_tokens": 1024,
          "temperature": 0.3,
          "system_prompt": ""
        }
      }
    }
  }
}
```

## 5. Error Handling

- If `model` is empty, raise `RuntimeError("LiteLLM model not configured")`.
- If `litellm.completion()` raises an exception (API key invalid, rate limit, etc.), re-raise as `RuntimeError` with the original message.
- Use `litellm.suppress_debug_info = True` to keep log output clean.
- Set `litellm.drop_params = True` so extra params for unsupported models are silently dropped.

## 6. Testing

- Unit test file: `tests/test_services/test_litellm_translate.py`
- Test service_id / display_name match.
- Test `translate()` raises when model is empty.
- Test `translate()` calls litellm.completion (mocked) and returns the expected text.
- Test `supported_languages()` returns expected structure.
- Test `config_schema()` returns valid JSON Schema.
- Test `translate_partial()` returns None.

## 7. Scope

This is focused on a single new service implementation. No changes to the pipeline, GUI, audio, or other subsystems beyond the config default and service registration wiring. The existing `gpt` placeholder is replaced cleanly.
