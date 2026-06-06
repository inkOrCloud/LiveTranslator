"""System tray icon for LiveTranslator."""

from __future__ import annotations

from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget


class TrayIcon(QSystemTrayIcon):
    """System tray icon with context menu for background operation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize tray icon.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)

        # Set icon
        self.setIcon(QIcon.fromTheme(
            "media-record",
            QIcon(":/qt-project.org/styles/commonstyle/images/"
                  "media-record-16.png"),
        ))

        self.setToolTip("LiveTranslator")

        # Build context menu
        menu = QMenu()
        self._show_action = QAction("Show/Hide", None)
        menu.addAction(self._show_action)
        menu.addSeparator()
        self._quit_action = QAction("Quit", None)
        menu.addAction(self._quit_action)
        self.setContextMenu(menu)

        self.show()
