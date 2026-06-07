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
    assert window.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)


def test_subtitle_window_show_latest_sentence(qapp: QApplication) -> None:
    """Displaying a sentence should show original + translation."""
    window = SubtitleWindow()
    window.show_latest("Hello world", "你好世界")
    assert window.isVisible()
    assert window._original_text == "Hello world"
    assert window._translated_text == "你好世界"


def test_subtitle_window_show_latest_updates(qapp: QApplication) -> None:
    """Calling show_latest again should replace previous text."""
    window = SubtitleWindow()
    window.show_latest("Hello", "你好")
    window.show_latest("Hello world", "你好世界")
    assert window._original_text == "Hello world"
    assert window._translated_text == "你好世界"


def test_subtitle_window_hide_on_empty(qapp: QApplication) -> None:
    """Calling show_latest with empty strings should hide the window."""
    window = SubtitleWindow()
    window.show_latest("", "")
    assert not window.isVisible()


def test_subtitle_window_clear(qapp: QApplication) -> None:
    """Clear should hide and reset text."""
    window = SubtitleWindow()
    window.show_latest("Hello", "你好")
    window.clear()
    assert not window.isVisible()
    assert window._original_text == ""
    assert window._translated_text == ""


def test_subtitle_window_default_hidden(qapp: QApplication) -> None:
    """SubtitleWindow should start hidden."""
    window = SubtitleWindow()
    assert not window.isVisible()


def test_subtitle_window_width_config(qapp: QApplication) -> None:
    """SubtitleWindow should respect width setting."""
    window = SubtitleWindow()
    window.set_window_width(400)
    assert window.width() == 400
