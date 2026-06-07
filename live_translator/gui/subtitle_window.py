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
        self._drag_offset: Any = None

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
        self._window_width = 720

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
        self._window_width = max(200, min(1600, width))
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

    def paintEvent(self, event: Any) -> None:
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

        # Draw text (y starts at padding top edge, AlignTop aligns text to top of rect)
        y = self._padding

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

        # Translated text in white
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
