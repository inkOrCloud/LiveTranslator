"""Shared QApplication fixture for GUI tests."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Create a shared QApplication for all GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
