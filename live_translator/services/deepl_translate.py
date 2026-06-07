"""DeepL API translation service implementation."""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


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
        logger.debug("DeepLTranslateService initialized: target_lang=%s",
                     self.config.get("target_lang", "ZH"))

    def translate(
        self, text: str, source_lang: str = "auto", target_lang: str | None = None
    ) -> str:
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

        logger.info(
            "DeepL translate: text_len=%d, source=%s, target=%s",
            len(text),
            source_lang,
            target,
        )
        logger.debug("DeepL input (first 100 chars): %s", text[:100])

        params: dict[str, str] = {
            "auth_key": api_key,
            "text": text,
            "target_lang": target.upper(),
        }
        if source_lang and source_lang.lower() != "auto":
            params["source_lang"] = source_lang.upper()

        try:
            logger.debug("Sending DeepL request to %s", self.BASE_URL)
            response = requests.post(self.BASE_URL, data=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            result = str(data["translations"][0]["text"])
            logger.info(
                "DeepL translation success: input_len=%d, output_len=%d",
                len(text),
                len(result),
            )
            logger.debug("DeepL output (first 100 chars): %s", result[:100])
        except requests.RequestException:
            msg = f"DeepL API request failed (text_len={len(text)})"
            logger.exception(msg)
            raise RuntimeError(msg) from None
        except (KeyError, ValueError):
            msg = "DeepL response parsing failed"
            logger.exception(msg)
            raise RuntimeError(msg) from None
        else:
            return result

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
