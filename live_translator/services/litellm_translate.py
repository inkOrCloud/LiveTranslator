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
