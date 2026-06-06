"""Tests for system tray icon."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from live_translator.gui.tray_icon import TrayIcon


def test_tray_icon_creation(qapp: QApplication) -> None:
    """TrayIcon should create without error."""
    icon = TrayIcon()
    assert icon.isVisible()
