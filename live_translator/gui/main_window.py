"""Main control panel window for LiveTranslator."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from live_translator.audio.virtual_speaker import VirtualSpeakerSource
from live_translator.config.manager import ConfigManager
from live_translator.gui.config_form import ConfigFormBuilder
from live_translator.services.registry import ServiceRegistry

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main control panel for the translation application."""

    _config_forms: dict[str, ConfigFormBuilder]

    def __init__(self, config: ConfigManager, registry: ServiceRegistry | None = None) -> None:
        """Initialize the main window.

        Args:
            config: Application configuration manager.
            registry: Service registry (created if None).
        """
        super().__init__()
        self._config = config
        self._registry = registry or ServiceRegistry()
        self._config_forms = {}

        self.setWindowTitle("LiveTranslator")
        self.setMinimumSize(500, 600)
        self.resize(500, 700)

        self._build_ui()
        logger.info("MainWindow initialized")

    def _build_ui(self) -> None:
        """Build the main window UI."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)

        # === Controls section ===
        controls = QHBoxLayout()
        self._btn_start = QPushButton("\u25b6 Start")
        self._btn_pause = QPushButton("\u23f8 Pause")
        self._btn_stop = QPushButton("\u23f9 Stop")
        controls.addWidget(self._btn_start)
        controls.addWidget(self._btn_pause)
        controls.addWidget(self._btn_stop)
        layout.addLayout(controls)

        # Status label
        self._status_label = QLabel("Status: Idle")
        layout.addWidget(self._status_label)

        # === Mode selector ===
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Subtitle", "Panel", "Dual"])
        mode_layout.addWidget(self._mode_combo)
        layout.addLayout(mode_layout)

        # === Output device selector ===
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output Device:"))
        self._output_sink_combo = QComboBox()
        self._output_sink_combo.setMinimumWidth(180)
        output_layout.addWidget(self._output_sink_combo, stretch=1)
        self._btn_refresh_sinks = QPushButton("\u21bb")
        self._btn_refresh_sinks.setToolTip("Refresh output device list")
        self._btn_refresh_sinks.setMaximumWidth(32)
        output_layout.addWidget(self._btn_refresh_sinks)
        layout.addLayout(output_layout)

        # === Service configuration (scrollable) ===
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # ASR section
        asr_label = QLabel("Speech Recognition Service")
        asr_label.setStyleSheet("font-weight: bold;")
        scroll_layout.addWidget(asr_label)

        self._asr_selector = QComboBox()
        scroll_layout.addWidget(self._asr_selector)

        self._asr_config_container = QWidget()
        self._asr_config_layout = QVBoxLayout(self._asr_config_container)
        scroll_layout.addWidget(self._asr_config_container)

        # Translator section
        t_label = QLabel("Translation Service")
        t_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        scroll_layout.addWidget(t_label)

        self._translator_selector = QComboBox()
        scroll_layout.addWidget(self._translator_selector)

        self._translator_config_container = QWidget()
        self._translator_config_layout = QVBoxLayout(
            self._translator_config_container,
        )
        scroll_layout.addWidget(self._translator_config_container)

        # Language selector
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("Source:"))
        self._source_lang = QComboBox()
        self._source_lang.addItem("Auto Detect", "auto")
        self._source_lang.addItem("English", "EN")
        self._source_lang.addItem("Chinese", "ZH")
        self._source_lang.addItem("Japanese", "JA")
        self._source_lang.addItem("Korean", "KO")
        lang_layout.addWidget(self._source_lang)

        lang_layout.addWidget(QLabel("Target:"))
        self._target_lang = QComboBox()
        self._target_lang.addItem("Chinese", "ZH")
        self._target_lang.addItem("English", "EN")
        self._target_lang.addItem("Japanese", "JA")
        self._target_lang.addItem("Korean", "KO")
        lang_layout.addWidget(self._target_lang)

        scroll_layout.addLayout(lang_layout)

        # Save button
        self._btn_save_config = QPushButton("Save Configuration")
        scroll_layout.addWidget(self._btn_save_config)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        # === Translation history ===
        history_label = QLabel("Translation History")
        history_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(history_label)

        self._history_list = QListWidget()
        layout.addWidget(self._history_list, stretch=1)

    # ------------------------------------------------------------------
    # Output device (sink) selector
    # ------------------------------------------------------------------

    def populate_sink_selector(self) -> None:
        """Query PulseAudio and fill the output device combo box."""
        self._output_sink_combo.clear()

        sinks = VirtualSpeakerSource.list_sinks()
        default_sink = VirtualSpeakerSource.get_default_sink_name()

        if not sinks:
            self._output_sink_combo.addItem("(No output devices found)", None)
            logger.warning("No PulseAudio sinks found")
            return

        # Add each sink; track whether we found the saved sink
        saved_sink = self._config.get("audio.virtual_speaker.output_sink", "")
        found_saved = False

        for sink in sinks:
            name = sink.get("name", "")
            desc = sink.get("description", name)
            display = f"{desc} ({name})" if desc != name else name

            self._output_sink_combo.addItem(display, name)

            if name == saved_sink:
                self._output_sink_combo.setCurrentIndex(self._output_sink_combo.count() - 1)
                found_saved = True

        # If saved sink wasn't found, try default sink
        if not found_saved and default_sink:
            idx = self._output_sink_combo.findData(default_sink)
            if idx >= 0:
                self._output_sink_combo.setCurrentIndex(idx)

        logger.debug(
            "Sink selector populated: %d sinks, selected=%s",
            self._output_sink_combo.count(),
            self._output_sink_combo.currentData(),
        )

    def get_output_sink(self) -> str | None:
        """Get the currently selected output sink name.

        Returns:
            Sink name string, or ``None`` if no device selected.
        """
        data = self._output_sink_combo.currentData()
        return str(data) if data and str(data) != "None" else None

    # ------------------------------------------------------------------
    # Service selectors
    # ------------------------------------------------------------------

    def populate_service_selectors(self) -> None:
        """Populate service selectors from registry."""
        self._asr_selector.clear()
        display_names = self._registry.list_display_names("asr")
        for sid, name in display_names.items():
            self._asr_selector.addItem(f"{name} ({sid})", sid)

        self._translator_selector.clear()
        display_names = self._registry.list_display_names("translator")
        for sid, name in display_names.items():
            self._translator_selector.addItem(f"{name} ({sid})", sid)

        # Set active service
        active_asr = self._config.get_active_service("asr")
        idx = self._asr_selector.findData(active_asr)
        if idx >= 0:
            self._asr_selector.setCurrentIndex(idx)
        else:
            logger.warning("Active ASR service '%s' not found in registry", active_asr)

        active_t = self._config.get_active_service("translator")
        idx = self._translator_selector.findData(active_t)
        if idx >= 0:
            self._translator_selector.setCurrentIndex(idx)
        else:
            logger.warning("Active translator service '%s' not found in registry", active_t)

        logger.debug(
            "Service selectors populated: asr=%s, translator=%s",
            active_asr,
            active_t,
        )

    def rebuild_config_forms(self) -> None:
        """Rebuild config forms for selected services."""
        # Clear existing config forms
        self._clear_layout(self._asr_config_layout)
        self._clear_layout(self._translator_config_layout)
        self._config_forms.clear()

        active_asr = self._asr_selector.currentData()
        active_t = self._translator_selector.currentData()
        logger.debug("Rebuilding config forms: asr=%s, translator=%s", active_asr, active_t)

        # Build ASR config form
        asr_service = self._registry.get("asr", active_asr)
        if asr_service is not None:
            schema = asr_service.config_schema()
            current_config = self._config.get_service_config("asr", active_asr)
            builder = ConfigFormBuilder(schema, current_config)
            form = builder.build()
            self._asr_config_layout.addWidget(form)
            self._config_forms[f"asr.{active_asr}"] = builder
            logger.debug("ASR config form built for '%s'", active_asr)

        # Build Translator config form
        t_service = self._registry.get("translator", active_t)
        if t_service is not None:
            schema = t_service.config_schema()
            current_config = self._config.get_service_config(
                "translator",
                active_t,
            )
            builder = ConfigFormBuilder(schema, current_config)
            form = builder.build()
            self._translator_config_layout.addWidget(form)
            self._config_forms[f"translator.{active_t}"] = builder
            logger.debug("Translator config form built for '%s'", active_t)

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        """Remove all widgets from a layout.

        Args:
            layout: The layout to clear.
        """
        while layout.count():
            item_w = layout.takeAt(0)
            w = item_w.widget() if item_w else None
            if w is not None:
                w.deleteLater()

    def add_history_entry(self, original: str, translated: str) -> None:
        """Add a translation result to the history list.

        Args:
            original: Original text.
            translated: Translated text.
        """
        item = QListWidgetItem(f"{original}\n\u2192 {translated}")
        self._history_list.insertItem(0, item)

        # Limit to 200 entries
        while self._history_list.count() > 200:
            self._history_list.takeItem(self._history_list.count() - 1)

        logger.debug("History entry added (%d total)", self._history_list.count())

    def get_languages(self) -> tuple[str, str]:
        """Get selected source and target language codes.

        Returns:
            Tuple of (source_code, target_code).
        """
        src = self._source_lang.currentData()
        tgt = self._target_lang.currentData()
        source = str(src) if src else "auto"
        target = str(tgt) if tgt else "ZH"
        logger.debug("Language selection: source=%s, target=%s", source, target)
        return source, target

    def set_status(self, text: str) -> None:
        """Set the status label text.

        Args:
            text: Status text to display.
        """
        self._status_label.setText(f"Status: {text}")
        logger.debug("Status updated: %s", text)
