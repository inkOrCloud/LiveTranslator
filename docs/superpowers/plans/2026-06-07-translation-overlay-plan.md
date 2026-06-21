# Translation Overlay Window Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-sentence SubtitleWindow with a new TranslationOverlayWindow that shows a scrollable translation history (top 2/3) and real-time ASR partial text (bottom 1/3) in a 1:2 aspect ratio floating overlay.

**Architecture:** Build three new classes — `HistoryItem` (single history entry), `PartialWidget` (real-time ASR display), and `TranslationOverlayWindow` (container with scroll area + divider + partial widget). Wire into `app.py` callbacks, remove old `SubtitleWindow` and its tests.

**Tech Stack:** PySide6 (Qt Widgets), pytest, UV project manager

**References:** `docs/superpowers/specs/2026-06-07-translation-overlay-design.md`

---

### File Structure

| File | Action | Responsibility |
|---|---|---|
| `live_translator/gui/translation_overlay.py` | **Create** | `ensure_xwayland_for_kde()`, `HistoryItem`, `PartialWidget`, `TranslationOverlayWindow` |
| `tests/test_gui/test_translation_overlay.py` | **Create** | Tests for all three classes |
| `live_translator/gui/app.py` | **Modify** | Wire overlay window, update callbacks |
| `live_translator/gui/subtitle_window.py` | **Delete** | Replaced entirely |
| `tests/test_gui/test_subtitle_window.py` | **Delete** | Old tests removed |

---

### Task 1: HistoryItem widget

**Files:**
- Create: `live_translator/gui/translation_overlay.py` (HistoryItem class only)
- Test: `tests/test_gui/test_translation_overlay.py` (HistoryItem tests)

- [ ] **Step 1: Write failing tests for HistoryItem**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gui/test_translation_overlay.py -v 2>&1`
Expected: ImportError — cannot import HistoryItem (file doesn't exist yet)

- [ ] **Step 3: Write minimal HistoryItem implementation**

At the top of `live_translator/gui/translation_overlay.py`:

```python
"""Floating translation overlay window with history and real-time ASR.

A frameless, always-on-top, translucent overlay that shows scrollable
translation history (top) and current ASR partial transcription (bottom)
in a 1:2 aspect ratio. Designed for KDE Wayland, auto-switches to
XWayland to ensure WindowStaysOnTopHint works.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


def ensure_xwayland_for_kde() -> None:
    """Restart the process under XWayland if running on KDE Wayland.

    KWin+Wayland ignores Qt's WindowStaysOnTopHint for Qt6 apps, so we
    need to switch to the xcb (XWayland) platform plugin.
    """
    if (
        os.environ.get("XDG_CURRENT_DESKTOP") == "KDE"
        and os.environ.get("XDG_SESSION_TYPE") == "wayland"
        and not os.environ.pop("_LIVETRANSLATOR_RESTARTED", None)
    ):
        os.environ["QT_QPA_PLATFORM"] = "xcb"
        os.environ["_LIVETRANSLATOR_RESTARTED"] = "1"
        logger.info("KDE Wayland detected - restarting under XWayland")
        os.execve(sys.executable, [sys.executable, *sys.argv], os.environ)  # noqa: S606


class HistoryItem(QFrame):
    """A single translation history entry showing original + translated text.

    Displays the original text (gray) and translated text (light gray)
    in a compact card with a left border. The latest item can be
    highlighted with a different border color.
    """

    def __init__(
        self,
        original: str,
        translated: str,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the history item.

        Args:
            original: Original (source language) text.
            translated: Translated text.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._latest = False

        self.setObjectName("HistoryItem")
        self.setStyleSheet("""
            HistoryItem {
                background: rgba(24, 24, 24, 230);
                border-left: 2px solid #555555;
                border-radius: 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        self._original_label = QLabel(original)
        self._original_label.setStyleSheet("color: #aaaaaa; font-size: 11px; background: transparent;")
        self._original_label.setWordWrap(True)

        self._translated_label = QLabel(translated)
        self._translated_label.setStyleSheet("color: #dddddd; font-size: 11px; background: transparent;")
        self._translated_label.setWordWrap(True)

        layout.addWidget(self._original_label)
        layout.addWidget(self._translated_label)

        logger.debug("HistoryItem created: original=%s, translated=%s",
                     original[:40], translated[:40])

    def set_latest(self, is_latest: bool) -> None:
        """Set whether this item is the most recent entry.

        Latest items get a cyan left border highlight.

        Args:
            is_latest: True if this is the most recent entry.
        """
        self._latest = is_latest
        if is_latest:
            self.setStyleSheet("""
                HistoryItem {
                    background: rgba(24, 24, 24, 230);
                    border-left: 2px solid #4fc3f7;
                    border-radius: 4px;
                }
            """)
        else:
            self.setStyleSheet("""
                HistoryItem {
                    background: rgba(24, 24, 24, 230);
                    border-left: 2px solid #555555;
                    border-radius: 4px;
                }
            """)
        logger.debug("HistoryItem latest=%s", is_latest)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gui/test_translation_overlay.py -v 2>&1`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd /home/ink/Desktop/develop/LiveTranslator && git add live_translator/gui/translation_overlay.py tests/test_gui/test_translation_overlay.py && git commit -m "feat: add HistoryItem widget for translation overlay"
```

---

### Task 2: PartialWidget

**Files:**
- Modify: `live_translator/gui/translation_overlay.py` (add PartialWidget class)
- Modify: `tests/test_gui/test_translation_overlay.py` (add PartialWidget tests)

- [ ] **Step 1: Write failing tests for PartialWidget**

Append to `tests/test_gui/test_translation_overlay.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gui/test_translation_overlay.py::test_partial_widget_creation -v 2>&1`
Expected: ImportError — cannot import PartialWidget

- [ ] **Step 3: Write PartialWidget implementation**

Append to `live_translator/gui/translation_overlay.py`:

```python
class PartialWidget(QFrame):
    """Widget displaying real-time ASR partial transcription.

    Shows the current partial/in-progress ASR transcription text
    in a dark green card with a green left border.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the partial widget.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setObjectName("PartialWidget")
        self.setStyleSheet("""
            PartialWidget {
                background: rgba(13, 40, 24, 217);
                border-left: 3px solid #4caf50;
                border-radius: 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)

        header = QLabel("实时转写")
        header.setStyleSheet("color: #666666; font-size: 9px; background: transparent;")
        layout.addWidget(header)

        self._partial_label = QLabel("")
        self._partial_label.setStyleSheet(
            "color: #8bc34a; font-size: 11px; background: transparent;",
        )
        self._partial_label.setWordWrap(True)
        layout.addWidget(self._partial_label)

        layout.addStretch()

        logger.debug("PartialWidget created")

    def show_text(self, text: str) -> None:
        """Update the displayed partial transcription text.

        Args:
            text: Partial transcription text to display.
        """
        self._partial_label.setText(text)
        logger.debug("PartialWidget updated: text=%s", text[:60])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gui/test_translation_overlay.py -v 2>&1`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
cd /home/ink/Desktop/develop/LiveTranslator && git add live_translator/gui/translation_overlay.py tests/test_gui/test_translation_overlay.py && git commit -m "feat: add PartialWidget for real-time ASR display"
```

---

### Task 3: TranslationOverlayWindow

**Files:**
- Modify: `live_translator/gui/translation_overlay.py` (add TranslationOverlayWindow)
- Modify: `tests/test_gui/test_translation_overlay.py` (add window tests)

- [ ] **Step 1: Write failing tests for TranslationOverlayWindow**

Append to `tests/test_gui/test_translation_overlay.py`:

```python
from live_translator.gui.translation_overlay import TranslationOverlayWindow


def test_overlay_creation(qapp: QApplication) -> None:
    """Window should have correct flags."""
    window = TranslationOverlayWindow()
    flags = window.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert window.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)


def test_overlay_default_hidden(qapp: QApplication) -> None:
    """Window should start hidden."""
    window = TranslationOverlayWindow()
    assert not window.isVisible()


def test_overlay_add_history(qapp: QApplication) -> None:
    """add_history should append a history item."""
    window = TranslationOverlayWindow()
    window.add_history("Hello", "你好")
    window.add_history("World", "世界")
    # Should have 2 HistoryItems in the scroll layout
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
    # Find the two items
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
    # All HistoryItems should be removed
    for i in range(window._scroll_layout.count()):
        widget = window._scroll_layout.itemAt(i).widget()
        assert not isinstance(widget, HistoryItem)


def test_overlay_history_cap(qapp: QApplication) -> None:
    """History should be capped at 500 entries."""
    window = TranslationOverlayWindow()
    window._max_history = 3  # Override for test speed
    for i in range(5):
        window.add_history(f"Item {i}", f"条目 {i}")
    # Count items
    count = 0
    for i in range(window._scroll_layout.count()):
        widget = window._scroll_layout.itemAt(i).widget()
        if isinstance(widget, HistoryItem):
            count += 1
    assert count <= 3


def test_overlay_aspect_ratio(qapp: QApplication) -> None:
    """Window should maintain 1:2 aspect ratio on resize."""
    window = TranslationOverlayWindow()
    window.setFixedWidth(300)
    window.resize(500, 300)
    # resizeEvent should enforce height = width * 2
    assert window.width() == 300
    assert window.height() == 600
```

- [ ] **Step 2: Run new tests to verify they fail**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gui/test_translation_overlay.py::test_overlay_creation -v 2>&1`
Expected: ImportError — cannot import TranslationOverlayWindow

- [ ] **Step 3: Write TranslationOverlayWindow implementation**

Append to `live_translator/gui/translation_overlay.py`:

```python
class TranslationOverlayWindow(QWidget):
    """A frameless, always-on-top, translucent overlay window.

    Displays scrollable translation history (top 2/3) and current ASR
    partial transcription (bottom 1/3) in a 1:2 aspect ratio.
    Draggable by left-click drag.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the overlay window.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)

        # Window flags
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Drag state
        self._dragging = False
        self._drag_offset: Any = None

        # Layout constants
        self._window_width = 300
        self._max_history = 500
        self._history_count = 0
        self._corner_radius = 10
        self._bg_opacity = 0.85

        # Fixed width
        self.setFixedWidth(self._window_width)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(0)

        # --- Scroll area for history ---
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; }
            QScrollBar:vertical {
                background: rgba(34, 34, 34, 180);
                width: 6px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #555555;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        self._scroll_content = QWidget()
        self._scroll_content.setStyleSheet("background: transparent;")
        self._scroll_layout = QVBoxLayout(self._scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(3)
        self._scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._scroll_area.setWidget(self._scroll_content)

        # --- Divider ---
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: #333333; border: none;")

        # --- Partial widget ---
        self._partial_widget = PartialWidget()

        # Add to main layout
        main_layout.addWidget(self._scroll_area, stretch=2)
        main_layout.addWidget(divider)
        main_layout.addWidget(self._partial_widget, stretch=1)

        # Set initial size (1:2 aspect ratio)
        self.setFixedHeight(self._window_width * 2)

        # Position at bottom-left of screen
        self._position_on_screen()

        # Start hidden
        self.hide()

        # Keep-alive timer
        self._keep_alive = QTimer(self)
        self._keep_alive.setInterval(2000)
        self._keep_alive.timeout.connect(self._raise_window)
        self._keep_alive.start()

        logger.debug(
            "TranslationOverlayWindow created: width=%d, height=%d",
            self._window_width,
            self._window_width * 2,
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
            self.setGeometry(100, 100, self._window_width, self._window_width * 2)
            return

        screen_rect: QRect = screen.availableGeometry()
        x = screen_rect.x() + 20
        y = screen_rect.bottom() - self._window_width * 2 - 20
        self.setGeometry(x, y, self._window_width, self._window_width * 2)
        logger.debug(
            "Overlay positioned: (%d, %d, %d, %d)",
            x, y,
            self._window_width,
            self._window_width * 2,
        )

    def _scroll_to_bottom(self) -> None:
        """Scroll the history area to the bottom."""
        scrollbar = self._scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # ── Public API ───────────────────────────────────────────────────

    def add_history(self, original: str, translated: str) -> None:
        """Add a translation pair to the history.

        The new entry is marked as the latest. Previous latest entry
        loses its highlight. Auto-scrolls to show the new entry.

        Args:
            original: Original (source language) text.
            translated: Translated text.
        """
        # Mark the previously latest item as not latest
        for i in range(self._scroll_layout.count()):
            widget = self._scroll_layout.itemAt(i).widget()
            if isinstance(widget, HistoryItem) and widget._latest:
                widget.set_latest(False)
                break

        # Create and add the new item
        item = HistoryItem(original, translated)
        item.set_latest(True)
        self._scroll_layout.addWidget(item)
        self._history_count += 1

        # Cap history at max entries
        while self._history_count > self._max_history:
            first_widget = self._scroll_layout.itemAt(0).widget()
            if isinstance(first_widget, HistoryItem):
                self._scroll_layout.removeWidget(first_widget)
                first_widget.deleteLater()
                self._history_count -= 1
            else:
                break

        # Auto-scroll to bottom
        QTimer.singleShot(50, self._scroll_to_bottom)

        # Ensure visible
        self.show()
        self.raise_()

        logger.debug(
            "History added: original=%s, total=%d",
            original[:40],
            self._history_count,
        )

    def show_partial(self, text: str) -> None:
        """Update the real-time ASR partial transcription text.

        Args:
            text: Current partial transcription text.
        """
        self._partial_widget.show_text(text)
        # Ensure visible when there's partial content
        if text:
            self.show()
            self.raise_()
        logger.debug("Partial updated: text=%s", text[:60])

    def clear(self) -> None:
        """Clear all history and partial text, then hide."""
        # Remove all HistoryItems from scroll layout
        i = 0
        while i < self._scroll_layout.count():
            widget = self._scroll_layout.itemAt(i).widget()
            if isinstance(widget, HistoryItem):
                self._scroll_layout.removeWidget(widget)
                widget.deleteLater()
            else:
                i += 1

        self._history_count = 0
        self._partial_widget.show_text("")
        self.hide()
        logger.debug("Overlay cleared and hidden")

    # ── Event handlers ───────────────────────────────────────────────

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        """Custom paint for translucent rounded background.

        Args:
            event: Paint event (unused).
        """
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(0, 0, 0, int(255 * self._bg_opacity))))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.drawRoundedRect(self.rect(), self._corner_radius, self._corner_radius)
        painter.end()

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        """Start window drag on left-click.

        Args:
            event: Mouse press event.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_offset = event.globalPosition() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802
        """Drag the window on mouse move while dragging.

        Args:
            event: Mouse move event.
        """
        if self._dragging and self._drag_offset is not None:
            self.move((event.globalPosition() - self._drag_offset).toPoint())
            event.accept()

    def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802
        """End window drag on left-button release.

        Args:
            event: Mouse release event.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._drag_offset = None
            event.accept()

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        """Enforce 1:2 aspect ratio on resize.

        Args:
            event: Resize event.
        """
        super().resizeEvent(event)
        # Maintain 1:2 aspect ratio based on width
        expected_height = self.width() * 2
        if self.height() != expected_height:
            self.setFixedHeight(expected_height)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_gui/test_translation_overlay.py -v 2>&1`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
cd /home/ink/Desktop/develop/LiveTranslator && git add live_translator/gui/translation_overlay.py tests/test_gui/test_translation_overlay.py && git commit -m "feat: add TranslationOverlayWindow with history and partial display"
```

---

### Task 4: Wire into app.py and clean up

**Files:**
- Modify: `live_translator/gui/app.py`
- Delete: `live_translator/gui/subtitle_window.py`
- Delete: `tests/test_gui/test_subtitle_window.py`

- [ ] **Step 1: Update app.py imports and references**

Changes in `live_translator/gui/app.py`:

1. Replace the TYPE_CHECKING import of `SubtitleWindow` with `TranslationOverlayWindow`:
```python
if TYPE_CHECKING:
    from live_translator.gui.main_window import MainWindow
    from live_translator.gui.translation_overlay import TranslationOverlayWindow
    from live_translator.gui.tray_icon import TrayIcon
```

2. Update `ensure_xwayland_for_kde` import:
```python
from live_translator.gui.translation_overlay import ensure_xwayland_for_kde
```

3. Change `__init__` variable:
```python
self._overlay_window: TranslationOverlayWindow | None = None
```

4. Update `_on_partial`:
```python
def _on_partial(self, text: str) -> None:
    if self._overlay_window:
        self._overlay_window.show_partial(text)
```

5. Update `_on_translation`:
```python
def _on_translation(self, original: str, translated: str) -> None:
    if self._overlay_window:
        self._overlay_window.add_history(original, translated)
        self._overlay_window.show_partial("")
    if self._main_window:
        self._main_window.add_history_entry(original, translated)
```

6. Update `_update_subtitle_visibility` → rename to `_update_overlay_visibility`:
```python
def _update_overlay_visibility(self) -> None:
    if self._main_window is None or self._overlay_window is None:
        return
    want_visible = (
        self._pipeline is not None
        and self._pipeline.status == PipelineStatus.STREAMING
        and self._main_window._subtitle_toggle.isChecked()
    )
    if want_visible:
        self._overlay_window.show()
        self._overlay_window.raise_()
    else:
        self._overlay_window.clear()
```

7. Update `_on_subtitle_toggled`:
```python
def _on_subtitle_toggled(self, checked: bool) -> None:  # noqa: FBT001
    self._update_overlay_visibility()
```

8. Update creation in `run()`:
```python
from live_translator.gui.translation_overlay import TranslationOverlayWindow

self._main_window = MainWindow(self._config, self._registry)
self._overlay_window = TranslationOverlayWindow()
```

9. Update the toggle wire:
```python
self._main_window._subtitle_toggle.toggled.connect(
    self._on_subtitle_toggled,
)
```

- [ ] **Step 2: Update `_update_subtitle_visibility` call in `_on_status_change`**

In `_on_status_change`, change:
```python
self._update_subtitle_visibility()
```
to:
```python
self._update_overlay_visibility()
```

- [ ] **Step 3: Delete old files**

Remove `live_translator/gui/subtitle_window.py` and `tests/test_gui/test_subtitle_window.py`.

- [ ] **Step 4: Run all tests to verify**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest -v 2>&1`
Expected: All tests pass (except potentially some unrelated failures)

- [ ] **Step 5: Run mypy check**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run mypy live_translator/gui/translation_overlay.py live_translator/gui/app.py 2>&1`
Expected: No type errors

- [ ] **Step 6: Commit**

```bash
cd /home/ink/Desktop/develop/LiveTranslator && git add live_translator/gui/translation_overlay.py tests/test_gui/test_translation_overlay.py live_translator/gui/app.py && git rm live_translator/gui/subtitle_window.py tests/test_gui/test_subtitle_window.py && git commit -m "feat: replace SubtitleWindow with TranslationOverlayWindow"
```
