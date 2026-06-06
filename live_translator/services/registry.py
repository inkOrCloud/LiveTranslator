"""Service registry for discovering and accessing ASR/Translator providers."""

from __future__ import annotations

from typing import Any


class ServiceRegistry:
    """Registry for pluable service implementations.

    Supports categorised registration (``"asr"``, ``"translator"``)
    and lookup by service_id.
    """

    def __init__(self) -> None:
        """Initialize registry with empty category buckets."""
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
        return {sid: svc.display_name for sid, svc in self._services.get(category, {}).items()}
