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
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Recursively merge override into base."""
        result: dict[str, Any] = {}
        all_keys = set(base) | set(override)
        for key in all_keys:
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
            if not isinstance(current, dict):
                return default
            if part not in current:
                return default
            current = current[part]
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
