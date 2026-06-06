"""Abstract interfaces for translation services."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Translator(Protocol):
    """Interface for text translation services."""

    service_id: str
    """Unique identifier for this service."""

    display_name: str
    """Human-readable name for UI."""

    config: dict[str, Any]
    """Current configuration dict for this service instance."""

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text from source language to target language.

        Args:
            text: The text to translate.
            source_lang: Source language code. Use ``"auto"`` for detection.
            target_lang: Target language code.

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
