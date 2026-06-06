"""Tests for service registry."""

from __future__ import annotations

from live_translator.services.registry import ServiceRegistry
from live_translator.services.asr import SpeechRecognizer, ASRSession
from live_translator.services.translator import Translator


def test_registry_register_and_get() -> None:
    """Services should be registered and retrievable by ID."""
    registry = ServiceRegistry()

    class FakeASR:
        service_id = "fake_asr"
        display_name = "Fake ASR"
        config = {}
        def create_session(self):
            raise NotImplementedError
        @classmethod
        def config_schema(cls):
            return {"type": "object", "properties": {}}

    registry.register("asr", FakeASR())
    result = registry.get("asr", "fake_asr")
    assert result is not None
    assert result.service_id == "fake_asr"


def test_registry_list_services() -> None:
    """list_services should return all registered service IDs."""
    registry = ServiceRegistry()

    class FakeASR:
        service_id = "asr_a"
        display_name = "ASR A"
        config = {}
        def create_session(self):
            raise NotImplementedError
        @classmethod
        def config_schema(cls):
            return {"type": "object", "properties": {}}

    class FakeASR2:
        service_id = "asr_b"
        display_name = "ASR B"
        config = {}
        def create_session(self):
            raise NotImplementedError
        @classmethod
        def config_schema(cls):
            return {"type": "object", "properties": {}}

    registry.register("asr", FakeASR())
    registry.register("asr", FakeASR2())
    ids = registry.list_services("asr")
    assert "asr_a" in ids
    assert "asr_b" in ids


def test_registry_get_unknown_service() -> None:
    """Getting an unknown service should return None."""
    registry = ServiceRegistry()
    assert registry.get("asr", "nonexistent") is None


def test_registry_list_display_names() -> None:
    """list_display_names should map IDs to display names."""
    registry = ServiceRegistry()

    class FakeASR:
        service_id = "my_asr"
        display_name = "My ASR Service"
        config = {}
        def create_session(self):
            raise NotImplementedError
        @classmethod
        def config_schema(cls):
            return {"type": "object", "properties": {}}

    registry.register("asr", FakeASR())
    names = registry.list_display_names("asr")
    assert names["my_asr"] == "My ASR Service"
