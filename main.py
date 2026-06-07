"""LiveTranslator - 同声传译实时翻译应用入口.

Usage:
    python main.py

Environment variables:
    LIVETRANSLATOR_CONFIG  : Path to config file (default: ~/.config/live-translator/config.json)
    LIVETRANSLATOR_LOG_LEVEL : Log level (DEBUG/INFO/WARNING/ERROR, default: INFO)
    LIVETRANSLATOR_LOG_FILE   : Optional log file path
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

from live_translator.gui.app import LiveTranslatorApp

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configure application-wide logging.

    Respects ``LIVETRANSLATOR_LOG_LEVEL`` and ``LIVETRANSLATOR_LOG_FILE``
    environment variables.
    """
    log_level_str = os.environ.get("LIVETRANSLATOR_LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    log_file = os.environ.get("LIVETRANSLATOR_LOG_FILE", "")

    handlers: list[logging.Handler] = []

    # Always log to stderr
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(log_level)
    handlers.append(stderr_handler)

    # Optional log file with rotation
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        handlers.append(file_handler)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True,
    )

    logger.debug(
        "Logging configured: level=%s, file=%s",
        log_level_str,
        log_file or "(stderr only)",
    )


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
        config_path = Path(env_path)
        logger.info("Using config from LIVETRANSLATOR_CONFIG: %s", config_path)
        return config_path

    config_path = Path.home() / ".config" / "live-translator" / "config.json"
    logger.debug("Default config path: %s", config_path)
    return config_path


def main() -> None:
    """Run the LiveTranslator application."""
    setup_logging()

    logger.info("Starting LiveTranslator v0.1.0")
    logger.debug("Python version: %s", sys.version)
    logger.debug("Platform: %s", sys.platform)

    config_path = get_config_path()

    if config_path.exists():
        logger.info("Config file found: %s (%d bytes)", config_path, config_path.stat().st_size)
    else:
        logger.warning("Config file not found at %s, will use defaults", config_path)

    app = LiveTranslatorApp(config_path)
    app.run()

    logger.info("LiveTranslator shutdown complete")


if __name__ == "__main__":
    main()
