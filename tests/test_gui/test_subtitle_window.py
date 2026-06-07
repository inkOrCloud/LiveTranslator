"""Tests for subtitle window."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from live_translator.gui.subtitle_window import SubtitleWindow


def test_subtitle_window_creation(qapp: QApplication) -> None:
    """SubtitleWindow should create with correct flags."""
    window = SubtitleWindow()
    flags = window.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert window.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


def test_subtitle_window_show_translation(qapp: QApplication) -> None:
    """Displaying text should not crash."""
    window = SubtitleWindow()
    window.show_translation("Hello world", "你好世界")
    assert window.isVisible()


def test_subtitle_window_show_partial(qapp: QApplication) -> None:
    """Showing partial text should not crash."""
    window = SubtitleWindow()
    window.show_partial("Hello wor")
    assert window.isVisible()


def test_subtitle_window_clear(qapp: QApplication) -> None:
    """Clear should hide the window."""
    window = SubtitleWindow()
    window.show_translation("Hello", "你好")
    window.clear()
    assert not window.isVisible()
