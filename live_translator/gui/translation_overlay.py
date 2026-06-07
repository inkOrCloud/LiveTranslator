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
