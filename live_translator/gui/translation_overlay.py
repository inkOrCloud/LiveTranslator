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
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QScrollArea,
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
        self._original_label.setStyleSheet(
            "color: #aaaaaa; font-size: 11px; background: transparent;",
        )
        self._original_label.setWordWrap(True)

        self._translated_label = QLabel(translated)
        self._translated_label.setStyleSheet(
            "color: #dddddd; font-size: 11px; background: transparent;",
        )
        self._translated_label.setWordWrap(True)

        layout.addWidget(self._original_label)
        layout.addWidget(self._translated_label)

        logger.debug(
            "HistoryItem created: original=%s, translated=%s",
            original[:40],
            translated[:40],
        )

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
            x,
            y,
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
