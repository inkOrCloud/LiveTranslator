"""LiveTranslator - 同声传译实时翻译应用入口.

Usage:
    python main.py
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from live_translator.gui.app import LiveTranslatorApp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_config_path() -> Path:
    """Determine the config file path.

    Priority:
    1. ``LIVETRANSLATOR_CONFIG`` environment variable
    2. ``~/.config/live-translator/config.json``

    Returns:
        Path to the config file.
    """
    env_path = os.environ.get("LIVETRANSLATOR_CONFIG")
    if env_path:
        return Path(env_path)

    return Path.home() / ".config" / "live-translator" / "config.json"


def main() -> None:
    """Run the LiveTranslator application."""
    config_path = get_config_path()
    logger.info("Starting LiveTranslator with config: %s", config_path)

    app = LiveTranslatorApp(config_path)
    app.run()


if __name__ == "__main__":
    main()
