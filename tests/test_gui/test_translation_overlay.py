"""Tests for translation overlay window components."""

from __future__ import annotations

from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from live_translator.gui.translation_overlay import HistoryItem


def test_history_item_creation(qapp: QApplication) -> None:
    """HistoryItem should display original and translated text."""
    item = HistoryItem("Hello world", "你好世界")
    assert item._original_label.text() == "Hello world"
    assert item._translated_label.text() == "你好世界"


def test_history_item_latest_styling(qapp: QApplication) -> None:
    """set_latest should toggle the latest-item styling flag."""
    item = HistoryItem("Hello", "你好")
    assert not item._latest
    item.set_latest(True)
    assert item._latest
    item.set_latest(False)
    assert not item._latest


def test_history_item_word_wrap(qapp: QApplication) -> None:
    """Labels should have word wrap enabled."""
    item = HistoryItem("Hello world", "你好世界")
    assert item._original_label.wordWrap()
    assert item._translated_label.wordWrap()


from live_translator.gui.translation_overlay import PartialWidget


def test_partial_widget_creation(qapp: QApplication) -> None:
    """PartialWidget should show label and empty partial text."""
    pw = PartialWidget()
    assert pw._partial_label.text() == ""


def test_partial_widget_show_text(qapp: QApplication) -> None:
    """show_text should update the displayed partial text."""
    pw = PartialWidget()
    pw.show_text("Hello world")
    assert pw._partial_label.text() == "Hello world"


def test_partial_widget_clear(qapp: QApplication) -> None:
    """show_text with empty string should clear the text."""
    pw = PartialWidget()
    pw.show_text("Hello")
    pw.show_text("")
    assert pw._partial_label.text() == ""


def test_partial_widget_word_wrap(qapp: QApplication) -> None:
    """Partial label should have word wrap enabled."""
    pw = PartialWidget()
    assert pw._partial_label.wordWrap()


from live_translator.gui.translation_overlay import TranslationOverlayWindow


def test_overlay_creation(qapp: QApplication) -> None:
    """Window should have correct flags."""
    window = TranslationOverlayWindow()
    flags = window.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert window.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    # Tool flag would lower Z-order priority in KDE Wayland — explicitly not set
    assert window.windowType() != Qt.WindowType.Tool


def test_overlay_default_hidden(qapp: QApplication) -> None:
    """Window should start hidden."""
    window = TranslationOverlayWindow()
    assert not window.isVisible()


def test_overlay_add_history(qapp: QApplication) -> None:
    """add_history should append a history item."""
    window = TranslationOverlayWindow()
    window.add_history("Hello", "你好")
    window.add_history("World", "世界")
    count = 0
    for i in range(window._scroll_layout.count()):
        widget = window._scroll_layout.itemAt(i).widget()
        if isinstance(widget, HistoryItem):
            count += 1
    assert count == 2


def test_overlay_add_history_latest_styling(qapp: QApplication) -> None:
    """Only the most recent item should have latest=True."""
    window = TranslationOverlayWindow()
    window.add_history("First", "第一")
    window.add_history("Second", "第二")
    items: list[HistoryItem] = []
    for i in range(window._scroll_layout.count()):
        widget = window._scroll_layout.itemAt(i).widget()
        if isinstance(widget, HistoryItem):
            items.append(widget)
    assert len(items) == 2
    assert not items[0]._latest
    assert items[1]._latest


def test_overlay_show_partial(qapp: QApplication) -> None:
    """show_partial should update the partial widget text."""
    window = TranslationOverlayWindow()
    window.show_partial("Hello world")
    assert window._partial_widget._partial_label.text() == "Hello world"


def test_overlay_clear(qapp: QApplication) -> None:
    """clear should remove all history, clear partial, and hide."""
    window = TranslationOverlayWindow()
    window.show()
    window.add_history("Test", "测试")
    window.show_partial("Partial")
    window.clear()
    assert not window.isVisible()
    assert window._partial_widget._partial_label.text() == ""
    for i in range(window._scroll_layout.count()):
        widget = window._scroll_layout.itemAt(i).widget()
        assert not isinstance(widget, HistoryItem)


def test_overlay_history_cap(qapp: QApplication) -> None:
    """History should be capped at max_history entries."""
    window = TranslationOverlayWindow()
    window._max_history = 3  # Override for test speed
    for i in range(5):
        window.add_history(f"Item {i}", f"条目 {i}")
    count = 0
    for i in range(window._scroll_layout.count()):
        widget = window._scroll_layout.itemAt(i).widget()
        if isinstance(widget, HistoryItem):
            count += 1
    assert count <= 3


def test_overlay_aspect_ratio(qapp: QApplication) -> None:
    """Window should maintain 1:2 aspect ratio on resize."""
    window = TranslationOverlayWindow()
    window.resize(500, 300)
    expected_height = window.width() * 2
    assert window.height() == expected_height


def test_overlay_raise_window_does_not_activate(qapp: QApplication) -> None:
    """_raise_window should only re-raise the window, never activate it.

    Calling activateWindow() steals keyboard focus from the current
    active window, disrupting user input. Use only raise_() to keep
    the overlay on top without stealing focus.
    """
    window = TranslationOverlayWindow()
    window.show()
    with patch.object(window, 'activateWindow') as mock_activate:
        window._raise_window()
        mock_activate.assert_not_called()
