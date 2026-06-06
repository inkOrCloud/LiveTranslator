"""Application entry point - initialises QApplication and main windows."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from live_translator.config.manager import ConfigManager
from live_translator.gui.config_form import ConfigFormBuilder
from live_translator.pipeline.events import PipelineStatus
from live_translator.pipeline.scheduler import PipelineScheduler
from live_translator.services.registry import ServiceRegistry

if TYPE_CHECKING:
    from live_translator.gui.main_window import MainWindow
    from live_translator.gui.subtitle_window import SubtitleWindow
    from live_translator.gui.tray_icon import TrayIcon


class LiveTranslatorApp:
    """Top-level application class that wires all components together."""

    def __init__(self, config_path: Path) -> None:
        """Initialize the application.

        Args:
            config_path: Path to the JSON configuration file.
        """
        self._config = ConfigManager(config_path)
        self._registry = ServiceRegistry()
        self._pipeline: PipelineScheduler | None = None
        self._main_window: MainWindow | None = None
        self._subtitle_window: SubtitleWindow | None = None
        self._tray_icon: TrayIcon | None = None
        self._poll_timer: QTimer | None = None
        self._config_forms: dict[str, ConfigFormBuilder] = {}

    def register_default_services(self) -> None:
        """Register built-in service implementations."""
        from live_translator.services.deepl_translate import DeepLTranslateService
        from live_translator.services.litellm_translate import LiteLLMTranslateService
        from live_translator.services.openai_realtime import OpenAIRealtimeService

        asr_config = self._config.get_service_config(
            "asr",
            "openai_realtime",
        )
        self._registry.register(
            "asr",
            OpenAIRealtimeService(asr_config),
        )

        t_config = self._config.get_service_config(
            "translator",
            "deepl",
        )
        self._registry.register(
            "translator",
            DeepLTranslateService(t_config),
        )

        t_litellm_config = self._config.get_service_config(
            "translator",
            "litellm",
        )
        self._registry.register(
            "translator",
            LiteLLMTranslateService(t_litellm_config),
        )

    def _on_start(self) -> None:
        """Handle start button click."""
        if self._pipeline is None:
            return
        src, tgt = self._main_window.get_languages() if self._main_window else ("auto", "ZH")
        self._pipeline.set_languages(src, tgt)
        self._pipeline.start()
        self._update_status_text()

    def _on_pause(self) -> None:
        """Handle pause button click."""
        if self._pipeline:
            self._pipeline.pause()
            self._update_status_text()

    def _on_stop(self) -> None:
        """Handle stop button click."""
        if self._pipeline:
            self._pipeline.stop()
            self._update_status_text()

    def _on_partial(self, text: str) -> None:
        """Handle partial ASR result.

        Args:
            text: Partial transcription text.
        """
        if self._subtitle_window:
            self._subtitle_window.show_partial(text)

    def _on_translation(self, original: str, translated: str) -> None:
        """Handle completed translation.

        Args:
            original: Original text.
            translated: Translated text.
        """
        if self._subtitle_window:
            self._subtitle_window.show_translation(original, translated)
        if self._main_window:
            self._main_window.add_history_entry(original, translated)

    def _on_status_change(self, status: PipelineStatus) -> None:
        """Handle pipeline status change.

        Args:
            status: New pipeline status.
        """
        self._update_status_text()

    def _on_error(self, message: str) -> None:
        """Handle pipeline error.

        Args:
            message: Error message.
        """
        if self._main_window:
            self._main_window.set_status(f"Error: {message}")

    def _update_status_text(self) -> None:
        """Update status label from pipeline state."""
        if self._main_window and self._pipeline:
            self._main_window.set_status(self._pipeline.status.name)

    def _on_save_config(self) -> None:
        """Save configuration from UI forms."""
        if not self._main_window:
            return

        # Save ASR config
        active_asr = self._main_window._asr_selector.currentData()
        form_key = f"asr.{active_asr}"
        if form_key in self._main_window._config_forms:
            builder = self._main_window._config_forms[form_key]
            values = builder.get_values()
            for key, val in values.items():
                self._config.set(
                    f"services.asr.providers.{active_asr}.{key}",
                    val,
                )
            self._config.set("services.asr.active", active_asr)

        # Save translator config
        active_t = self._main_window._translator_selector.currentData()
        form_key = f"translator.{active_t}"
        if form_key in self._main_window._config_forms:
            builder = self._main_window._config_forms[form_key]
            values = builder.get_values()
            for key, val in values.items():
                self._config.set(
                    f"services.translator.providers.{active_t}.{key}",
                    val,
                )
            self._config.set("services.translator.active", active_t)

        self._config.save()

        # Reload services with updated config
        self.register_default_services()
        self._rebuild_pipeline()

    def _rebuild_pipeline(self) -> None:
        """Rebuild the pipeline with current service instances."""
        asr_service = self._registry.get(
            "asr",
            self._config.get_active_service("asr"),
        )
        t_service = self._registry.get(
            "translator",
            self._config.get_active_service("translator"),
        )
        if asr_service is None or t_service is None:
            return

        from live_translator.audio.system_monitor import SystemMonitor

        audio = SystemMonitor(
            sample_rate=self._config.get("audio.sample_rate", 16000),
        )

        self._pipeline = PipelineScheduler(audio, asr_service, t_service)
        self._pipeline.on_partial = self._on_partial
        self._pipeline.on_translation = self._on_translation
        self._pipeline.on_status_change = self._on_status_change
        self._pipeline.on_error = self._on_error

    def _show_windows(self) -> None:
        """Show both main and subtitle windows."""
        if self._main_window:
            self._main_window.show()
        if self._subtitle_window:
            self._subtitle_window.show()

    def run(self) -> None:
        """Start the Qt application event loop."""
        import sys

        app = QApplication(sys.argv)

        from live_translator.gui.main_window import MainWindow
        from live_translator.gui.subtitle_window import SubtitleWindow
        from live_translator.gui.tray_icon import TrayIcon

        self._main_window = MainWindow(self._config, self._registry)
        self._subtitle_window = SubtitleWindow()

        # Register default services
        self.register_default_services()

        # Populate UI
        self._main_window.populate_service_selectors()
        self._main_window.rebuild_config_forms()

        # Build pipeline
        self._rebuild_pipeline()

        # Wire signals
        self._main_window._btn_start.clicked.connect(self._on_start)
        self._main_window._btn_pause.clicked.connect(self._on_pause)
        self._main_window._btn_stop.clicked.connect(self._on_stop)
        self._main_window._btn_save_config.clicked.connect(
            self._on_save_config,
        )
        self._main_window._asr_selector.currentIndexChanged.connect(
            self._main_window.rebuild_config_forms,
        )
        self._main_window._translator_selector.currentIndexChanged.connect(
            self._main_window.rebuild_config_forms,
        )

        # Poll ASR session messages via timer
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_asr_session)
        self._poll_timer.start(50)

        # Tray icon
        self._tray_icon = TrayIcon(self._main_window)
        self._tray_icon._show_action.triggered.connect(
            self._show_windows,
        )
        self._tray_icon._quit_action.triggered.connect(app.quit)

        # Show windows
        self._main_window.show()
        self._subtitle_window.show()

        sys.exit(app.exec())

    def _poll_asr_session(self) -> None:
        """Periodically poll ASR session for incoming messages."""
        if self._pipeline is None:
            return
        session = getattr(self._pipeline, "_asr_session", None)
        if session is not None and hasattr(session, "poll"):
            session.poll()
