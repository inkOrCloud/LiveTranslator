# Subtitle Toggle Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change the 3-mode subtitle selector to an on/off toggle, and redesign the subtitle window as a small draggable always-on-top overlay showing only the latest sentence (original + translation).

**Architecture:** SubtitleWindow becomes a compact floating overlay (QWidget) that is draggable, always-on-top, auto-wrapping text, showing max 4 lines. It only shows when the app is streaming and the toggle is ON. MainWindow replaces "Mode" QComboBox with a QCheckBox. App.py wires toggle + pipeline status to subtitle visibility.

**Tech Stack:** PySide6, KDE Wayland (with XWayland fallback for always-on-top), QWindow.startSystemMove() for drag

---

### Task 1: Rewrite SubtitleWindow as compact floating overlay

**Files:**
- Modify: `live_translator/gui/subtitle_window.py`
- Test: `tests/test_gui/test_subtitle_window.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run test to verify they fail**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gui/test_subtitle_window.py -v 2>&1`
Expected: Various failures (missing methods, wrong attribute names)

- [ ] **Step 3: Write the new SubtitleWindow implementation**

```python
"""Floating subtitle overlay window.

A compact, draggable, always-on-top overlay that shows the latest sentence
(original + translation) with auto word-wrap. Designed for KDE Wayland,
auto-switches to XWayland to ensure WindowStaysOnTopHint works.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

logger = logging.getLogger(__name__)


# ── Auto-restart to XWayland on KDE Wayland ──────────────────────────
_AUTO_RESTARTED = os.environ.pop("_LIVETRANSLATOR_SUBTITLE_RESTARTED", None)
if (
    os.environ.get("XDG_CURRENT_DESKTOP") == "KDE"
    and os.environ.get("XDG_SESSION_TYPE") == "wayland"
    and not _AUTO_RESTARTED
):
    os.environ["QT_QPA_PLATFORM"] = "xcb"
    os.environ["_LIVETRANSLATOR_SUBTITLE_RESTARTED"] = "1"
    # Only restart if this is the main process
    if "--subtitle-only" not in sys.argv:
        logger.info("KDE Wayland detected - restarting under XWayland for subtitle window")
        os.execve(sys.executable, [sys.executable] + sys.argv, os.environ)


class SubtitleWindow(QWidget):
    """A compact, draggable, always-on-top floating overlay window.

    Shows only the latest sentence (original + translation) with auto
    word-wrap, max 4 lines of text. Draggable by left-click drag.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the subtitle window.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)

        # Window flags: frameless, always-on-top, no taskbar entry
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        # Transparent background for custom painting
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Don't steal focus
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Drag state
        self._dragging = False
        self._drag_offset = None

        # Text state
        self._original_text: str = ""
        self._translated_text: str = ""

        # Layout constants
        self._font_size = 14
        self._padding = 10
        self._line_spacing = 4
        self._corner_radius = 8
        self._bg_opacity = 0.85
        self._max_lines = 4
        self._window_width = 360

        # Set up font
        self._font = QFont("Noto Sans CJK SC, Noto Sans, sans-serif", self._font_size)
        self._font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)

        # Fixed window width
        self.setFixedWidth(self._window_width)

        # Position at bottom-left of screen
        self._position_on_screen()

        # Start hidden
        self.hide()

        # Keep-alive timer to maintain always-on-top
        self._keep_alive = QTimer(self)
        self._keep_alive.setInterval(2000)
        self._keep_alive.timeout.connect(self._raise_window)
        self._keep_alive.start()

        logger.debug(
            "SubtitleWindow created: font_size=%d, width=%d",
            self._font_size,
            self._window_width,
        )

    def _raise_window(self) -> None:
        """Periodically re-raise window to stay on top."""
        if self.isVisible():
            self.raise_()
            self.activateWindow()

    def _position_on_screen(self) -> None:
        """Position at bottom-left of primary screen."""
        screen = QApplication.primaryScreen()
        if screen is None:
            self.setGeometry(100, 100, self._window_width, 120)
            return

        screen_rect: QRect = screen.availableGeometry()
        x = screen_rect.x() + 20
        y = screen_rect.bottom() - 150
        self.setGeometry(x, y, self._window_width, 120)
        logger.debug("SubtitleWindow positioned: (%d, %d, %d, 120)", x, y, self._window_width)

    def set_window_width(self, width: int) -> None:
        """Set the subtitle window width.

        Args:
            width: Width in pixels.
        """
        self._window_width = max(200, min(800, width))
        self.setFixedWidth(self._window_width)
        self.adjustSize()
        self.update()

    # ── Public API ───────────────────────────────────────────────────

    def show_latest(self, original: str, translated: str) -> None:
        """Display the latest sentence pair.

        Only the most recent original + translated text is shown.
        If both strings are empty, the window is hidden.

        Args:
            original: Original (source language) text.
            translated: Translated (target language) text.
        """
        self._original_text = original
        self._translated_text = translated

        if not original and not translated:
            self.hide()
            logger.debug("Subtitle hidden (empty text)")
            return

        self.adjustSize()
        self.show()
        self.raise_()
        self.update()
        logger.debug(
            "Subtitle shown: orig=%d chars, trans=%d chars",
            len(original),
            len(translated),
        )

    def clear(self) -> None:
        """Clear text and hide the window."""
        self._original_text = ""
        self._translated_text = ""
        self.hide()
        logger.debug("Subtitle window cleared and hidden")

    # ── Drag support ─────────────────────────────────────────────────

    def mousePressEvent(self, event: Any) -> None:
        """Start drag on left-click.

        Args:
            event: Mouse press event.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            # Try native system move first (Wayland compatible)
            wh = self.windowHandle()
            if wh and wh.startSystemMove():
                event.accept()
                return
            # Fallback for X11
            self._dragging = True
            self._drag_offset = event.position().toPoint()
            event.accept()

    def mouseMoveEvent(self, event: Any) -> None:
        """Handle drag movement (X11 fallback).

        Args:
            event: Mouse move event.
        """
        if self._dragging and event.buttons() == Qt.MouseButton.LeftButton:
            if self._drag_offset is not None:
                self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event: Any) -> None:
        """End drag on left-button release.

        Args:
            event: Mouse release event.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._drag_offset = None
            event.accept()

    # ── Painting ─────────────────────────────────────────────────────

    def adjustSize(self) -> None:
        """Calculate and set window height based on text content."""
        metrics = QFontMetrics(self._font)
        line_height = metrics.height() + self._line_spacing
        available_width = self._window_width - 2 * self._padding

        # Estimate how many lines we need
        total_lines = 0
        if self._original_text:
            orig_lines = self._count_wrap_lines(self._original_text, available_width, metrics)
            total_lines += orig_lines
        if self._translated_text:
            trans_lines = self._count_wrap_lines(self._translated_text, available_width, metrics)
            total_lines += trans_lines

        total_lines = min(total_lines, self._max_lines)
        total_lines = max(total_lines, 1)  # at least 1 line

        height = total_lines * line_height + 2 * self._padding
        self.setFixedHeight(height)

    @staticmethod
    def _count_wrap_lines(text: str, available_width: int, metrics: QFontMetrics) -> int:
        """Count how many lines text needs with word wrap.

        Args:
            text: Text to measure.
            available_width: Available width in pixels.
            metrics: QFontMetrics for the current font.

        Returns:
            Number of lines needed.
        """
        if not text:
            return 0
        words = text.split()
        if not words:
            return 1

        lines = 1
        current_width = 0
        for word in words:
            word_width = metrics.horizontalAdvance(word + " ")
            if current_width + word_width > available_width:
                lines += 1
                current_width = word_width
            else:
                current_width += word_width
        return lines

    @staticmethod
    def _wrap_text(text: str, available_width: int, metrics: QFontMetrics) -> list[str]:
        """Wrap text to fit available width.

        Args:
            text: Text to wrap.
            available_width: Available width in pixels.
            metrics: QFontMetrics for the current font.

        Returns:
            List of wrapped lines.
        """
        if not text:
            return [""]
        words = text.split()
        if not words:
            return [""]

        lines: list[str] = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip() if current_line else word
            if metrics.horizontalAdvance(test_line) > available_width and current_line:
                lines.append(current_line)
                current_line = word
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)
        return lines or [""]

    def paintEvent(self, event: Any) -> None:  # noqa: N802, PLR0915
        """Custom paint for translucent rounded background and text.

        Args:
            event: Paint event (unused).
        """
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        metrics = QFontMetrics(self._font)
        line_height = metrics.height() + self._line_spacing
        available_width = self._window_width - 2 * self._padding

        # Draw semi-transparent rounded background
        painter.setBrush(QBrush(QColor(0, 0, 0, int(255 * self._bg_opacity))))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.drawRoundedRect(self.rect(), self._corner_radius, self._corner_radius)

        # Draw text
        y = self._padding + metrics.ascent()

        # Original text in light gray
        if self._original_text:
            orig_lines = self._wrap_text(self._original_text, available_width, metrics)
            painter.setPen(QColor(200, 200, 200))
            painter.setFont(self._font)
            for line in orig_lines:
                painter.drawText(
                    self._padding, y,
                    available_width, line_height,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                    line,
                )
                y += line_height

        # Translated text in white (with separator if original exists)
        if self._translated_text:
            trans_lines = self._wrap_text(self._translated_text, available_width, metrics)
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(self._font)
            for line in trans_lines:
                painter.drawText(
                    self._padding, y,
                    available_width, line_height,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                    line,
                )
                y += line_height

        painter.end()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gui/test_subtitle_window.py -v 2>&1`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
cd /home/ink/Desktop/develop/LiveTranslator && \
git add live_translator/gui/subtitle_window.py tests/test_gui/test_subtitle_window.py && \
git commit -m "feat: rewrite subtitle window as compact draggable floating overlay"
```

### Task 2: Add subtitle toggle to MainWindow

**Files:**
- Modify: `live_translator/gui/main_window.py`
- Test: `tests/test_gui/test_main_window.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for main control panel window."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtWidgets import QApplication

from live_translator.config.manager import ConfigManager
from live_translator.gui.main_window import MainWindow


def _make_config() -> ConfigManager:
    """Create a temporary config for tests."""
    tmp = tempfile.mkdtemp()
    return ConfigManager(Path(tmp) / "config.json")


def test_main_window_creation(qapp: QApplication) -> None:
    """MainWindow should create without error."""
    window = MainWindow(_make_config())
    assert window.windowTitle() == "LiveTranslator"


def test_main_window_has_subtitle_toggle(qapp: QApplication) -> None:
    """MainWindow should have a subtitle toggle checkbox."""
    window = MainWindow(_make_config())
    assert hasattr(window, "_subtitle_toggle")
    assert window._subtitle_toggle.isChecked()  # should be on by default


def test_main_window_no_mode_combo(qapp: QApplication) -> None:
    """MainWindow should NOT have the old mode combo."""
    window = MainWindow(_make_config())
    assert not hasattr(window, "_mode_combo") or window._mode_combo is None


def test_main_window_subtitle_toggle_signal(qapp: QApplication) -> None:
    """Subtitle toggle should emit toggled signal."""
    window = MainWindow(_make_config())
    assert window._subtitle_toggle.toggled is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gui/test_main_window.py -v 2>&1`
Expected: Failures about missing `_subtitle_toggle` attribute

- [ ] **Step 3: Replace Mode combo with subtitle toggle in MainWindow**

In `_build_ui`, replace:
```python
        # === Mode selector ===
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Subtitle", "Panel", "Dual"])
        mode_layout.addWidget(self._mode_combo)
        layout.addLayout(mode_layout)
```

With:
```python
        # === Subtitle overlay toggle ===
        self._subtitle_toggle = QCheckBox("Show Subtitle Overlay")
        self._subtitle_toggle.setChecked(True)
        self._subtitle_toggle.setToolTip(
            "Show floating subtitle window when translating"
        )
        layout.addWidget(self._subtitle_toggle)
```

Add imports (add QCheckBox to the existing import list from QtWidgets).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gui/test_main_window.py -v 2>&1`
Expected: All tests pass

Add `QCheckBox` to the imports from `PySide6.QtWidgets` in `main_window.py`.

- [ ] **Step 5: Commit**

```bash
cd /home/ink/Desktop/develop/LiveTranslator && \
git add live_translator/gui/main_window.py tests/test_gui/test_main_window.py && \
git commit -m "feat: replace 3-mode selector with subtitle toggle checkbox"
```

### Task 3: Wire subtitle toggle and pipeline status in App

**Files:**
- Modify: `live_translator/gui/app.py`
- Test: (no new tests needed, existing integration covers)

- [ ] **Step 1: Add subtitle visibility logic to App**

The subtitle window should:
- Only show when `_subtitle_toggle.isChecked()` AND pipeline status is STREAMING
- Track both the toggle state and pipeline status

Add to `LiveTranslatorApp`:

```python
    def _on_subtitle_toggled(self, checked: bool) -> None:
        """Handle subtitle toggle change.

        Args:
            checked: True if subtitle should be shown when active.
        """
        self._update_subtitle_visibility()

    def _update_subtitle_visibility(self) -> None:
        """Update subtitle window visibility based on toggle + pipeline state."""
        if self._main_window is None or self._subtitle_window is None:
            return
        shown = (
            self._main_window._subtitle_toggle.isChecked()
            and self._pipeline is not None
            and self._pipeline.status == PipelineStatus.STREAMING
        )
        if shown:
            # Don't force-show if there's no text yet
            pass
        else:
            self._subtitle_window.hide()

    def _on_status_change(self, status: PipelineStatus) -> None:
        """Handle pipeline status change.

        Args:
            status: New pipeline status.
        """
        logger.info("Pipeline status changed: %s", status.name)
        self._update_status_text()
        self._update_subtitle_visibility()
```

And wire in `run()`:
```python
        # Wire subtitle toggle
        self._main_window._subtitle_toggle.toggled.connect(
            self._on_subtitle_toggled
        )
```

The existing `_on_status_change` callback needs to be updated to also call `_update_subtitle_visibility`.

- [ ] **Step 2: Update existing `_on_status_change` in app.py**

Find `_on_status_change` (it currently exists) and modify it to call `_update_subtitle_visibility()`.

Let me check the current method:

```python
    def _on_status_change(self, status: PipelineStatus) -> None:
        """Handle pipeline status change."""
        logger.info("Pipeline status changed: %s", status.name)
        self._update_status_text()
```

Add `self._update_subtitle_visibility()` call.

- [ ] **Step 3: Run existing tests to verify nothing broke**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest -v 2>&1`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
cd /home/ink/Desktop/develop/LiveTranslator && \
git add live_translator/gui/app.py && \
git commit -m "feat: wire subtitle toggle and pipeline status to subtitle visibility"
```

### Task 4: Run linting and final verification

- [ ] **Step 1: Run ruff check**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run ruff check live_translator/gui/subtitle_window.py live_translator/gui/main_window.py live_translator/gui/app.py 2>&1`
Expected: No errors or warnings

- [ ] **Step 2: Run all tests**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest -v 2>&1`
Expected: All tests pass

- [ ] **Step 3: Commit (if lint fixes were made)**

```bash
cd /home/ink/Desktop/develop/LiveTranslator && \
git add live_translator/gui/ tests/ && \
git commit -m "style: fix lint issues"
```
