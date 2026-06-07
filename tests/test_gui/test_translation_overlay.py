"""Tests for translation overlay window components."""

from __future__ import annotations

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
