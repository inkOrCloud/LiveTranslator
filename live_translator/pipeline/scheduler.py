"""Pipeline scheduler orchestrating audio capture, ASR, and translation."""

from __future__ import annotations

import logging
from collections.abc import Callable

from live_translator.audio.source import AudioSource
from live_translator.pipeline.events import PipelineStatus
from live_translator.services.asr import ASRSession, SpeechRecognizer
from live_translator.services.translator import Translator

logger = logging.getLogger(__name__)


class PipelineScheduler:
    """Orchestrates the audio -> ASR -> translation pipeline.

    Manages the lifecycle of audio capture and ASR sessions,
    routing final transcription results through the translator
    and emitting results via callbacks.
    """

    def __init__(
        self,
        audio_source: AudioSource,
        asr_service: SpeechRecognizer,
        translator: Translator,
    ) -> None:
        """Initialize the pipeline scheduler.

        Args:
            audio_source: Source for audio capture.
            asr_service: ASR service for speech recognition.
            translator: Translation service.
        """
        self._audio_source = audio_source
        self._asr_service = asr_service
        self._translator = translator
        self._asr_session: ASRSession | None = None
        self._status = PipelineStatus.IDLE
        self._source_lang = "auto"
        self._target_lang = "ZH"

        # Callbacks for pipeline consumers (GUI)
        self.on_partial: Callable[[str], None] | None = None
        self.on_translation: Callable[[str, str], None] | None = None
        self.on_status_change: Callable[[PipelineStatus], None] | None = None
        self.on_error: Callable[[str], None] | None = None

        logger.info(
            "PipelineScheduler created: asr=%s, translator=%s",
            getattr(asr_service, "service_id", "?"),
            getattr(translator, "service_id", "?"),
        )

    @property
    def status(self) -> PipelineStatus:
        """Current pipeline status."""
        return self._status

    def start(self) -> None:
        """Start the pipeline: begin audio capture and ASR session."""
        if self._status == PipelineStatus.STREAMING:
            logger.warning("Pipeline already streaming, ignoring start")
            return

        logger.info(
            "Starting pipeline: source_lang=%s, target_lang=%s",
            self._source_lang,
            self._target_lang,
        )

        self._asr_session = self._asr_service.create_session()
        self._asr_session.on_partial(self._on_asr_partial)
        self._asr_session.on_final(self._on_asr_final)
        self._asr_session.on_error(self._on_asr_error)
        logger.debug("ASR session created and callbacks registered")

        self._audio_source.start(self._on_audio_chunk)

        self._set_status(PipelineStatus.STREAMING)
        logger.info("Pipeline started successfully")

    def stop(self) -> None:
        """Stop the pipeline and release resources."""
        logger.info("Stopping pipeline")
        self._audio_source.stop()

        if self._asr_session is not None:
            self._asr_session.close()
            self._asr_session = None
            logger.debug("ASR session closed")

        self._set_status(PipelineStatus.IDLE)
        logger.info("Pipeline stopped")

    def pause(self) -> None:
        """Pause the pipeline (stop audio capture, keep session)."""
        if self._status != PipelineStatus.STREAMING:
            logger.debug("Ignoring pause: current status=%s", self._status.name)
            return
        self._audio_source.stop()
        self._set_status(PipelineStatus.PAUSED)
        logger.info("Pipeline paused (audio capture stopped, session preserved)")

    def resume(self) -> None:
        """Resume the pipeline."""
        if self._status != PipelineStatus.PAUSED:
            logger.debug("Ignoring resume: current status=%s", self._status.name)
            return
        if self._asr_session is None or not self._asr_session.is_alive:
            # Session expired, create a new one
            logger.info("ASR session expired or None, creating new session")
            self._asr_session = self._asr_service.create_session()
            self._asr_session.on_partial(self._on_asr_partial)
            self._asr_session.on_final(self._on_asr_final)
            self._asr_session.on_error(self._on_asr_error)
            logger.debug("New ASR session created during resume")

        self._audio_source.start(self._on_audio_chunk)
        self._set_status(PipelineStatus.STREAMING)
        logger.info("Pipeline resumed")

    def set_languages(self, source: str, target: str) -> None:
        """Set source and target languages.

        Args:
            source: Source language code (``"auto"`` for detection).
            target: Target language code.
        """
        logger.debug("Pipeline languages set: source=%s, target=%s", source, target)
        self._source_lang = source
        self._target_lang = target

    def _on_audio_chunk(self, chunk: bytes) -> None:
        """Handle incoming audio chunk from AudioSource.

        Args:
            chunk: PCM16 mono audio data chunk.
        """
        if self._asr_session is not None and self._status == PipelineStatus.STREAMING:
            self._asr_session.send_audio(chunk)

    def _on_asr_partial(self, text: str) -> None:
        """Handle partial ASR result.

        In synchronous mode, partial results are shown as transcription
        hints but not translated.

        Args:
            text: Partial transcription text.
        """
        if self.on_partial:
            self.on_partial(text)

    def _on_asr_final(self, text: str) -> None:
        """Handle final ASR result and trigger translation.

        Args:
            text: Final transcription text.
        """
        if not text.strip():
            logger.debug("Empty final transcript, skipping translation")
            return

        logger.info("Final transcript received (%d chars): %s...", len(text), text[:60])

        if self.on_partial:
            self.on_partial(text)

        try:
            logger.debug(
                "Translating: source_lang=%s, target_lang=%s",
                self._source_lang,
                self._target_lang,
            )
            translated = self._translator.translate(
                text,
                source_lang=self._source_lang,
                target_lang=self._target_lang,
            )
            if self.on_translation:
                self.on_translation(text, translated)
        except Exception as exc:
            logger.exception("Translation failed: text_len=%d", len(text))
            if self.on_error:
                self.on_error(f"Translation failed: {exc}")

    def _on_asr_error(self, exc: Exception) -> None:
        """Handle ASR session error.

        Args:
            exc: The exception that occurred.
        """
        logger.error("ASR error in pipeline: %s: %s", type(exc).__name__, exc)
        if self.on_error:
            self.on_error(str(exc))

    def _set_status(self, status: PipelineStatus) -> None:
        """Update pipeline status and notify listeners.

        Args:
            status: New pipeline status.
        """
        old_status = self._status
        self._status = status
        logger.debug("Pipeline status: %s -> %s", old_status.name, status.name)
        if self.on_status_change:
            self.on_status_change(status)
