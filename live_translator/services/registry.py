"""Service registry for discovering and accessing ASR/Translator providers."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


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
        logger.debug("ServiceRegistry initialized")

    def register(self, category: str, service: Any) -> None:
        """Register a service under a category.

        Args:
            category: ``"asr"`` or ``"translator"``.
            service: An object conforming to the category's protocol.
        """
        if category not in self._services:
            self._services[category] = {}
        self._services[category][service.service_id] = service
        logger.info(
            "Service registered: category=%s, id=%s, name=%s",
            category,
            service.service_id,
            getattr(service, "display_name", service.service_id),
        )

    def get(self, category: str, service_id: str) -> Any | None:
        """Get a registered service by category and ID.

        Args:
            category: ``"asr"`` or ``"translator"``.
            service_id: The service's unique identifier.

        Returns:
            The service instance, or None if not found.
        """
        service = self._services.get(category, {}).get(service_id)
        if service is None:
            logger.warning("Service not found: category=%s, id=%s", category, service_id)
        else:
            logger.debug("Service lookup: category=%s, id=%s -> found", category, service_id)
        return service

    def list_services(self, category: str) -> list[str]:
        """List all registered service IDs in a category.

        Args:
            category: ``"asr"`` or ``"translator"``.

        Returns:
            A list of service ID strings.
        """
        service_ids = list(self._services.get(category, {}).keys())
        logger.debug("List services: category=%s -> %s", category, service_ids)
        return service_ids

    def list_display_names(self, category: str) -> dict[str, str]:
        """Map service IDs to display names in a category.

        Args:
            category: ``"asr"`` or ``"translator"``.

        Returns:
            Dict mapping service_id -> display_name.
        """
        result = {sid: svc.display_name for sid, svc in self._services.get(category, {}).items()}
        logger.debug("List display names: category=%s -> %s", category, result)
        return result
