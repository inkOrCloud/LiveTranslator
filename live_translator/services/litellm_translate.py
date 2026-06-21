"""LiteLLM-based translation service supporting 100+ LLM models.

Supports optional conversation context enhancement that preserves transcription
history across a session, using a 4-layer context structure:

1. Prompt layer — system translation instruction
2. Background/compression layer — condensed summary of older conversation
3. Historical text layer — recent transcription → translation pairs
4. Current text layer — the text currently being translated
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

import litellm

from live_translator.services.context import TranslationContext

if TYPE_CHECKING:
    from litellm.types.utils import ModelResponse

logger = logging.getLogger(__name__)


class LiteLLMTranslateService:
    """Translator implementation using LiteLLM SDK.

    Supports any model supported by LiteLLM (OpenAI, Anthropic, Google,
    open-source, custom endpoints, etc.). LiteLLM automatically routes
    to the correct API format based on the model name.

    When ``enable_context`` is ``True`` (default), the service maintains a
    :class:`TranslationContext` that accumulates transcription history and
    injects it into subsequent translation prompts for context-aware output.
    """

    service_id = "litellm"
    display_name = "LiteLLM (多模型)"

    _NO_MODEL_MSG = "LiteLLM model not configured"

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
            "enable_context": True,
            "max_context_tokens": 4000,
        }
        self._context = TranslationContext(
            max_context_tokens=self.config.get("max_context_tokens", 4000),
        )
        logger.debug(
            "LiteLLMTranslateService initialized: model=%s, api_base=%s, "
            "enable_context=%s, max_context_tokens=%s",
            self.config.get("model", "unknown"),
            self.config.get("api_base", "(default)"),
            self.config.get("enable_context", True),
            self.config.get("max_context_tokens", 4000),
        )

    # ── Public API ──────────────────────────────────────────────

    def translate(
        self,
        text: str,
        source_lang: str = "auto",
        target_lang: str | None = None,
    ) -> str:
        """Translate text via LiteLLM completion, with optional context.

        When context is enabled, the method:
        1. Checks if compression is needed (if so, compresses first)
        2. Builds context-aware messages with the 4-layer structure
        3. Calls litellm.completion
        4. Stores the (original, translated) pair in history

        When context is disabled, behaves identically to the original
        implementation.

        Args:
            text: Text to translate.
            source_lang: Source language code (``"auto"`` for detection).
            target_lang: Target language code or name.

        Returns:
            Translated text.

        Raises:
            RuntimeError: If model is not configured or API call fails.
        """
        model = self.config.get("model", "")
        if not model:
            raise RuntimeError(self._NO_MODEL_MSG)

        target = target_lang or self.config.get("target_lang", "Chinese")

        logger.info(
            "LiteLLM translate: text_len=%d, source=%s, target=%s, model=%s",
            len(text),
            source_lang,
            target,
            model,
        )
        logger.debug("Translation input (first 100 chars): %s", text[:100])

        # Build messages (context-aware or original)
        enable_context = self.config.get("enable_context", True)
        if enable_context:
            messages = self._build_context_messages(
                text, source_lang, target,
            )
        else:
            messages = self._build_default_messages(text, source_lang, target)

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
            logger.debug("Using custom API base: %s", api_base)

        max_tokens = self.config.get("max_tokens")
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        temperature = self.config.get("temperature")
        if temperature is not None:
            kwargs["temperature"] = temperature

        try:
            response = cast("ModelResponse", litellm.completion(**kwargs))
            result = str(response.choices[0].message.content)
            logger.info(
                "LiteLLM translation success: input_len=%d, output_len=%d",
                len(text),
                len(result),
            )
            logger.debug("Translation output (first 100 chars): %s", result[:100])
        except Exception:
            msg = f"LiteLLM translation failed (model={model}, text_len={len(text)})"
            logger.exception(msg)
            raise RuntimeError(msg) from None

        # Store the translation pair in context
        if enable_context:
            self._context.add_pair(text, result)

        return result

    def translate_partial(
        self,
        text: str,
        source_lang: str = "auto",
        target_lang: str | None = None,
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
            temperature, system_prompt, enable_context, and
            max_context_tokens fields.
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
                "enable_context": {
                    "type": "boolean",
                    "title": "Enable Context Enhancement",
                    "description": (
                        "When enabled, transcription history is preserved and "
                        "injected into the prompt for context-aware translation. "
                        "The context is built from prompt + background summary "
                        "+ recent history + current text."
                    ),
                    "default": True,
                },
                "max_context_tokens": {
                    "type": "integer",
                    "title": "Max Context Tokens",
                    "description": (
                        "Estimated token threshold for context compression. "
                        "When the context exceeds this limit, the background "
                        "summary and history are combined and compressed into "
                        "a new background summary, and history is cleared."
                    ),
                    "default": 4000,
                    "minimum": 512,
                    "maximum": 128000,
                },
            },
            "required": ["model"],
        }

    # ── Context management ──────────────────────────────────────

    @property
    def translation_context(self) -> TranslationContext:
        """Access the internal :class:`TranslationContext` instance."""
        return self._context

    def reset_context(self) -> None:
        """Reset the translation context (background + history).

        Call this when starting a new session or changing languages.
        """
        self._context.reset()
        logger.info("Translation context reset by user request")

    # ── Internal helpers ────────────────────────────────────────

    def _build_context_messages(
        self,
        text: str,
        source_lang: str,
        target: str,
    ) -> list[dict[str, str]]:
        """Build messages with the 4-layer context structure.

        Steps:
        1. Check if compression is needed; if so, compress first
        2. Build the context block (background + history + current text)
        3. Wrap into the appropriate message format

        Args:
            text: Current text to translate.
            source_lang: Source language.
            target: Target language.

        Returns:
            Messages list for litellm.completion.
        """
        system_prompt = self.config.get("system_prompt", "")

        # Step 1: compress if needed
        if self._context.needs_compression(system_prompt, text):
            logger.info(
                "Context compression triggered: %d history items, "
                "background_len=%d",
                self._context.item_count,
                len(self._context.background),
            )
            self._compress_context()

        # Step 2: build context block
        context_block = self._context.build_context_block(text)

        # Step 3: wrap into messages
        if system_prompt:
            user_content = system_prompt.format(
                source_lang=source_lang if source_lang != "auto" else "auto-detected",
                target_lang=target,
                text=context_block,
            )
            return [{"role": "user", "content": user_content}]

        return [
            {
                "role": "system",
                "content": (
                    f"You are a professional translator. Translate the following text "
                    f"from {source_lang if source_lang != 'auto' else 'auto-detected'} "
                    f"to {target}. "
                    f"Use the provided conversation background and history to ensure "
                    f"contextually consistent translations. "
                    f"Return ONLY the translated text, no explanations, no notes."
                ),
            },
            {"role": "user", "content": context_block},
        ]

    def _build_default_messages(
        self,
        text: str,
        source_lang: str,
        target: str,
    ) -> list[dict[str, str]]:
        """Build messages without context enhancement (original behavior).

        Args:
            text: Current text to translate.
            source_lang: Source language.
            target: Target language.

        Returns:
            Messages list for litellm.completion.
        """
        system_prompt = self.config.get("system_prompt", "")
        if system_prompt:
            user_content = system_prompt.format(
                source_lang=source_lang if source_lang != "auto" else "auto-detected",
                target_lang=target,
                text=text,
            )
            return [{"role": "user", "content": user_content}]

        return [
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

    def _compress_context(self) -> None:
        """Compress the current background + history into a new background.

        Calls litellm.completion with a compression prompt, stores the
        result as the new background, and clears the history layer.

        If the API call fails, the existing context is preserved and
        an error is logged.
        """
        try:
            compression_messages = self._context.build_compression_messages()

            model = self.config.get("model", "")
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": compression_messages,
            }

            api_key = self.config.get("api_key", "")
            if api_key:
                kwargs["api_key"] = api_key

            api_base = self.config.get("api_base", "")
            if api_base:
                kwargs["api_base"] = api_base

            # Use lower max_tokens for compression to keep it concise
            kwargs["max_tokens"] = 2048

            logger.info("Compressing translation context: model=%s", model)
            response = cast("ModelResponse", litellm.completion(**kwargs))
            compressed = str(response.choices[0].message.content).strip()

            if compressed:
                self._context.background = compressed
                self._context.clear_history()
                logger.info(
                    "Context compressed: new background_len=%d, history cleared",
                    len(compressed),
                )
            else:
                logger.warning("Compression returned empty result, context unchanged")
        except Exception:
            logger.exception(
                "Context compression failed, preserving existing context"
            )
