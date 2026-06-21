"""Application entry point - initialises QApplication and main windows."""

from __future__ import annotations

import logging
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
    from live_translator.gui.translation_overlay import TranslationOverlayWindow
    from live_translator.gui.tray_icon import TrayIcon

from live_translator.gui.translation_overlay import ensure_xwayland_for_kde

logger = logging.getLogger(__name__)


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
        self._overlay_window: TranslationOverlayWindow | None = None
        self._tray_icon: TrayIcon | None = None
        self._poll_timer: QTimer | None = None
        self._config_forms: dict[str, ConfigFormBuilder] = {}

        logger.info("LiveTranslatorApp initialized: config=%s", config_path)

    def register_default_services(self) -> None:
        """Register built-in service implementations."""
        logger.info("Registering default services")

        from live_translator.services.deepl_translate import DeepLTranslateService
        from live_translator.services.litellm_translate import LiteLLMTranslateService
        from live_translator.services.openai_realtime import OpenAIRealtimeService
        from live_translator.services.qwen_asr import QwenASRService

        asr_config = self._config.get_service_config(
            "asr",
            "openai_realtime",
        )
        self._registry.register(
            "asr",
            OpenAIRealtimeService(asr_config),
        )
        qwen_asr_config = self._config.get_service_config(
            "asr",
            "qwen_asr",
        )
        self._registry.register(
            "asr",
            QwenASRService(qwen_asr_config),
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

        logger.debug("Default services registered: %s",
                     self._registry.list_services("asr") +
                    self._registry.list_services("translator"))

    def _on_start(self) -> None:
        """Handle start button click."""
        if self._pipeline is None:
            logger.warning("Start requested but pipeline is None")
            return

        # If pipeline was previously streaming, do nothing (already running)
        from live_translator.pipeline.events import PipelineStatus
        if self._pipeline.status == PipelineStatus.STREAMING:
            logger.debug("Pipeline already streaming, ignoring start")
            return

        # Rebuild pipeline so SoundcardSource picks up the latest
        # capture device from the GUI selector
        self._rebuild_pipeline()

        src, tgt = self._main_window.get_languages() if self._main_window else ("auto", "ZH")
        self._pipeline.set_languages(src, tgt)
        logger.info("Pipeline start triggered: source=%s, target=%s", src, tgt)
        self._pipeline.start()
        self._update_status_text()

    def _on_pause(self) -> None:
        """Handle pause button click."""
        if self._pipeline:
            logger.info("Pipeline pause triggered")
            self._pipeline.pause()
            self._update_status_text()
        else:
            logger.warning("Pause requested but pipeline is None")

    def _on_stop(self) -> None:
        """Handle stop button click."""
        if self._pipeline:
            logger.info("Pipeline stop triggered")
            self._pipeline.stop()
            self._update_status_text()
        else:
            logger.warning("Stop requested but pipeline is None")

    def _on_partial(self, text: str) -> None:
        """Handle partial ASR result.

        Args:
            text: Partial transcription text.
        """
        if self._overlay_window:
            self._overlay_window.show_partial(text)

    def _on_translation(self, original: str, translated: str) -> None:
        """Handle completed translation.

        Args:
            original: Original text.
            translated: Translated text.
        """
        if self._overlay_window:
            self._overlay_window.add_history(original, translated)
        if self._overlay_window:
            self._overlay_window.show_partial("")
        if self._main_window:
            self._main_window.add_history_entry(original, translated)

    def _on_status_change(self, status: PipelineStatus) -> None:
        """Handle pipeline status change.

        Args:
            status: New pipeline status.
        """
        logger.info("Pipeline status changed: %s", status.name)
        self._update_status_text()
        self._update_overlay_visibility()

    def _on_error(self, message: str) -> None:
        """Handle pipeline error.

        Args:
            message: Error message.
        """
        logger.error("Pipeline error: %s", message)
        if self._main_window:
            self._main_window.set_status(f"Error: {message}")

    def _on_subtitle_toggled(self, checked: bool) -> None:  # noqa: FBT001
        """Handle subtitle toggle change.

        Args:
            checked: True if subtitle should be shown when active.
        """
        del checked
        self._update_overlay_visibility()

    def _update_overlay_visibility(self) -> None:
        """Update subtitle window visibility based on toggle + pipeline state."""
        if self._main_window is None or self._overlay_window is None:
            return
        show = (
            self._main_window._subtitle_toggle.isChecked()
            and self._pipeline is not None
            and self._pipeline.status == PipelineStatus.STREAMING
        )
        if show:
            self._overlay_window.show()
            self._overlay_window.raise_()
        else:
            self._overlay_window.clear()

    def _update_status_text(self) -> None:
        """Update status label from pipeline state."""
        if self._main_window and self._pipeline:
            self._main_window.set_status(self._pipeline.status.name)

    def _on_save_config(self) -> None:
        """Save configuration from UI forms."""
        if not self._main_window:
            logger.warning("Save config requested but main window is None")
            return

        logger.info("Saving configuration from UI")

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
            logger.info("ASR config saved: active=%s", active_asr)

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
            logger.info("Translator config saved: active=%s", active_t)

        # Save capture device selection
        if self._main_window:
            device_name = self._main_window.get_capture_device()
            self._config.set(
                "audio.capture.device_name",
                device_name or "",
            )
            logger.info("Capture device saved: %s", device_name or "(auto)")

        self._config.save()

        # Reload services with updated config
        logger.info("Reloading services with updated config")
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
            logger.error(
                "Cannot rebuild pipeline: asr=%s, translator=%s",
                asr_service is not None,
                t_service is not None,
            )
            return

        sample_rate = self._config.get("audio.sample_rate", 16000)

        from live_translator.audio.soundcard_source import SoundcardSource

        # Determine the capture device from the GUI selection or config
        device_name = None
        if self._main_window:
            device_name = self._main_window.get_capture_device()

        audio = SoundcardSource(
            device_name=device_name,
            sample_rate=sample_rate,
        )
        logger.info(
            "Using SoundcardSource: device_name=%s",
            device_name or "(auto)",
        )

        self._pipeline = PipelineScheduler(audio, asr_service, t_service)
        self._pipeline.on_partial = self._on_partial
        self._pipeline.on_translation = self._on_translation
        self._pipeline.on_status_change = self._on_status_change
        self._pipeline.on_error = self._on_error

        logger.info(
            "Pipeline rebuilt: asr=%s, translator=%s, sample_rate=%d",
            asr_service.service_id,
            t_service.service_id,
            sample_rate,
        )

    def _show_windows(self) -> None:
        """Show both main and subtitle windows."""
        if self._main_window:
            self._main_window.show()
        # Subtitle visibility is controlled by toggle + pipeline state
        logger.debug("Windows shown")

    def run(self) -> None:
        """Start the Qt application event loop."""
        import sys

        # Ensure XWayland on KDE Wayland for proper window-on-top behavior
        ensure_xwayland_for_kde()

        logger.info("Starting Qt application event loop")
        app = QApplication(sys.argv)

        from live_translator.gui.main_window import MainWindow
        from live_translator.gui.translation_overlay import TranslationOverlayWindow
        from live_translator.gui.tray_icon import TrayIcon

        self._main_window = MainWindow(self._config, self._registry)
        self._overlay_window = TranslationOverlayWindow()

        logger.debug("MainWindow and TranslationOverlayWindow created")

        # Register default services
        self.register_default_services()

        # Populate UI
        self._main_window.populate_service_selectors()
        self._main_window.rebuild_config_forms()

        # Populate output device selector before building pipeline
        # so _rebuild_pipeline can read the selected output sink
        self._main_window.populate_capture_devices()

        # Build pipeline
        self._rebuild_pipeline()

        # Wire subtitle toggle
        self._main_window._subtitle_toggle.toggled.connect(
            self._on_subtitle_toggled,
        )

        # Wire signals
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
        logger.debug("Signal connections established")

        # Poll ASR session messages via timer
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_asr_session)
        self._poll_timer.start(50)
        logger.debug("ASR poll timer started (50ms interval)")

        # Tray icon
        self._tray_icon = TrayIcon(self._main_window)
        self._tray_icon._show_action.triggered.connect(
            self._show_windows,
        )
        self._tray_icon._quit_action.triggered.connect(app.quit)
        logger.debug("Tray icon set up")

        # Show windows
        self._main_window.show()
        # Subtitle visibility is controlled by toggle + pipeline state
        logger.info("Application windows displayed")

        sys.exit(app.exec())

    def _poll_asr_session(self) -> None:
        """Periodically poll ASR session for incoming messages."""
        if self._pipeline is None:
            return
        session = getattr(self._pipeline, "_asr_session", None)
        if session is not None and hasattr(session, "poll"):
            session.poll()
