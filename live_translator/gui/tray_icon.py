"""System tray icon for LiveTranslator."""

from __future__ import annotations

import logging

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

logger = logging.getLogger(__name__)


class TrayIcon(QSystemTrayIcon):
    """System tray icon with context menu for background operation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize tray icon.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)

        # Set icon
        icon = QIcon.fromTheme(
            "media-record",
            QIcon(":/qt-project.org/styles/commonstyle/images/media-record-16.png"),
        )
        self.setIcon(icon)

        self.setToolTip("LiveTranslator")

        # Build context menu
        menu = QMenu()
        self._show_action = QAction("Show/Hide", None)
        self._show_action.triggered.connect(self._on_show_hide)
        menu.addAction(self._show_action)
        menu.addSeparator()
        self._quit_action = QAction("Quit", None)
        self._quit_action.triggered.connect(self._on_quit)
        menu.addAction(self._quit_action)
        self.setContextMenu(menu)

        # Connect activation signal (click on tray icon)
        self.activated.connect(self._on_activated)

        self.show()
        logger.info("Tray icon created and shown")

    def _on_show_hide(self) -> None:
        """Handle show/hide action from context menu."""
        logger.debug("Tray icon: show/hide triggered")

    def _on_quit(self) -> None:
        """Handle quit action from context menu."""
        logger.info("Tray icon: quit triggered")

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation (click).

        Args:
            reason: The activation reason.
        """
        logger.debug("Tray icon activated: %s", reason.name if hasattr(reason, "name") else reason)
