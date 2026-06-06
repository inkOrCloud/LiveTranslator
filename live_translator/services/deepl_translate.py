"""DeepL API translation service implementation."""

from __future__ import annotations

from typing import Any

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

        import requests
        response = requests.post(self.BASE_URL, data=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return str(data["translations"][0]["text"])

    def translate_partial(self, text: str, source_lang: str = "auto",
                          target_lang: str | None = None) -> str | None:
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
