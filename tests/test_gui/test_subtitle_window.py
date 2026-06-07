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


def test_subtitle_window_show_empty(qapp: QApplication) -> None:
    """SubtitleWindow.show() should work even without text content."""
    window = SubtitleWindow()
    window.show()
    assert window.isVisible()
    window.hide()
    assert not window.isVisible()

# ── Font size ────────────────────────────────────────────────────────

def test_subtitle_window_font_size_smaller(qapp: QApplication) -> None:
    """Font size should be 12 (one step smaller than current 14)."""
    window = SubtitleWindow()
    assert window._font_size == 12


# ── Max lines ────────────────────────────────────────────────────────

def test_subtitle_window_max_lines_six(qapp: QApplication) -> None:
    """Max total lines should be 6."""
    window = SubtitleWindow()
    assert window._max_lines == 6


# ── Ellipsis folding (truncation helper) ─────────────────────────────

def test_truncate_with_ellipsis_under_limit(qapp: QApplication) -> None:
    """Lines under max_lines should pass through unchanged."""
    window = SubtitleWindow()
    lines = ["line one", "line two"]
    result = window._truncate_with_ellipsis(lines, 3)
    assert result == ["line one", "line two"]


def test_truncate_with_ellipsis_exact_limit(qapp: QApplication) -> None:
    """Lines exactly at max_lines should pass through unchanged."""
    window = SubtitleWindow()
    lines = ["line one", "line two", "line three"]
    result = window._truncate_with_ellipsis(lines, 3)
    assert result == ["line one", "line two", "line three"]


def test_truncate_with_ellipsis_over_limit(qapp: QApplication) -> None:
    """Lines over max_lines should be truncated with '...' on the last line."""
    window = SubtitleWindow()
    lines = ["line one", "line two", "line three", "line four"]
    result = window._truncate_with_ellipsis(lines, 3)
    assert result == ["line one", "line two", "line three..."]


def test_truncate_with_ellipsis_empty(qapp: QApplication) -> None:
    """Empty list should return empty list."""
    window = SubtitleWindow()
    result = window._truncate_with_ellipsis([], 3)
    assert result == []


def test_truncate_with_ellipsis_max_lines_one(qapp: QApplication) -> None:
    """Truncation with max_lines=1 should collapse to a single line with ellipsis."""
    window = SubtitleWindow()
    lines = ["a", "b", "c"]
    result = window._truncate_with_ellipsis(lines, 1)
    assert result == ["a..."]


def test_subtitle_window_original_folded_at_three_lines(qapp: QApplication) -> None:
    """Original text wrapping >3 lines should be folded to 3 with ellipsis."""
    window = SubtitleWindow()
    # Use a narrow width to force wrapping
    long_text = "Hello world this is a very long sentence that should wrap into many lines " * 5
    # Force window width small to trigger wrapping
    window.set_window_width(200)
    available_width = window._window_width - 2 * window._padding
    from PySide6.QtGui import QFontMetrics
    metrics = QFontMetrics(window._font)
    lines = window._wrap_text(long_text, available_width, metrics)
    # Ensure it wraps to more than 3 lines
    assert len(lines) > 3, f"Expected >3 wrapped lines, got {len(lines)}"
    folded = window._truncate_with_ellipsis(lines, 3)
    assert len(folded) == 3
    assert folded[-1].endswith("...")


def test_subtitle_window_translation_folded_at_three_lines(qapp: QApplication) -> None:
    """Translation text wrapping >3 lines should be folded to 3 with ellipsis."""
    window = SubtitleWindow()
    long_text = "这是一个非常长的中文句子它应该会换行成很多行这是一个非常长的中文句子它应该会换行成很多行 " * 5
    window.set_window_width(200)
    available_width = window._window_width - 2 * window._padding
    from PySide6.QtGui import QFontMetrics
    metrics = QFontMetrics(window._font)
    lines = window._wrap_text(long_text, available_width, metrics)
    assert len(lines) > 3, f"Expected >3 wrapped lines, got {len(lines)}"
    folded = window._truncate_with_ellipsis(lines, 3)
    assert len(folded) == 3
    assert folded[-1].endswith("...")
