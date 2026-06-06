"""Tests for system tray icon."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from live_translator.gui.tray_icon import TrayIcon


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """Create QApplication for widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_tray_icon_creation(qapp: QApplication) -> None:
    """TrayIcon should create without error."""
    icon = TrayIcon()
    assert icon.isVisible()
