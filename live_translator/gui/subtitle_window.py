"""Floating subtitle overlay window.

A frameless, transparent, click-through window that stays on top of all
other windows and displays translation results near the bottom of the
screen, similar to video subtitles.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget


class SubtitleWindow(QWidget):
    """A floating, transparent subtitle overlay window."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the subtitle window.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)

        # Window flags: frameless, always-on-top, tool (no taskbar entry)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        # Transparent background for custom painting
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Let mouse events pass through to windows beneath
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # Appearance settings
        self._font_size = 28
        self._opacity = 0.9
        self._max_lines = 3
        self._line_spacing = 8

        # Translation history (tuples of original, translated)
        self._entries: list[tuple[str, str]] = []
        self._partial_text: str = ""

        # Auto-hide timer
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._on_hide_timeout)

        # Set up font
        self._font = QFont("Noto Sans CJK SC, Noto Sans, sans-serif", self._font_size)
        self._font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)

        # Position at bottom of screen
        self._position_on_screen()

    def _position_on_screen(self) -> None:
        """Position the window at the bottom of the primary screen."""
        screen = QApplication.primaryScreen()
        if screen is None:
            self.setGeometry(0, 0, 800, 200)
            return

        screen_rect: QRect = screen.availableGeometry()
        height = 200
        self.setGeometry(
            screen_rect.x(),
            screen_rect.bottom() - height - 10,
            screen_rect.width(),
            height,
        )

    def set_font_size(self, size: int) -> None:
        """Set subtitle font size.

        Args:
            size: Font size in points.
        """
        self._font_size = size
        self._font.setPointSize(size)
        self.update()

    def set_opacity(self, value: float) -> None:
        """Set subtitle background opacity.

        Args:
            value: Opacity from 0.0 to 1.0.
        """
        self._opacity = max(0.0, min(1.0, value))
        self.update()

    def show_partial(self, text: str) -> None:
        """Display partial/in-progress transcription.

        Args:
            text: Partial transcription text.
        """
        self._partial_text = text
        self.show()
        self.update()

    def show_translation(self, original: str, translated: str) -> None:
        """Display a complete translation result.

        Args:
            original: Original (source language) text.
            translated: Translated (target language) text.
        """
        self._entries.append((original, translated))
        if len(self._entries) > self._max_lines:
            self._entries = self._entries[-self._max_lines :]

        self._partial_text = ""
        self.show()
        self.update()

        # Auto-hide after 30 seconds of no updates
        self._hide_timer.start(30000)

    def clear(self) -> None:
        """Clear all displayed text."""
        self._entries.clear()
        self._partial_text = ""
        self._hide_timer.stop()
        self.hide()

    def _on_hide_timeout(self) -> None:
        """Auto-hide the window after timeout."""
        self.hide()

    def paintEvent(self, event: Any) -> None:
        """Custom paint for semi-transparent subtitle background and text.

        Args:
            event: Paint event (unused).
        """
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Calculate required height based on content
        metrics = QFontMetrics(self._font)
        line_height = metrics.height() + self._line_spacing
        content_lines = len(self._entries)
        if self._partial_text:
            content_lines += 1
        total_height = max(10, content_lines * line_height + 20)

        # Semi-transparent background
        painter.setBrush(QBrush(QColor(0, 0, 0, int(255 * self._opacity))))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.drawRoundedRect(0, self.height() - total_height, self.width(), total_height, 6, 6)

        # Draw entries from bottom up
        y = self.height() - 15  # bottom padding
        for original, translated in reversed(self._entries):
            # Original text (gray)
            painter.setPen(QColor(200, 200, 200))
            painter.setFont(self._font)
            painter.drawText(
                20,
                y - line_height,
                self.width() - 40,
                line_height,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                original,
            )

            # Separator and translated text (white)
            painter.setPen(QColor(255, 255, 255))
            display_text = f" \u2500 {translated}" if translated else ""
            painter.drawText(
                20,
                y,
                self.width() - 40,
                line_height,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                display_text,
            )
            y -= 2 * line_height

        # Partial text (most recent, bottom)
        if self._partial_text:
            painter.setPen(QColor(180, 180, 180))
            partial_display = f"{self._partial_text} \u2026"
            painter.drawText(
                20,
                y,
                self.width() - 40,
                line_height,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                partial_display,
            )

        painter.end()
