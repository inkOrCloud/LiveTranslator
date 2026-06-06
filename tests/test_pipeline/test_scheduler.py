"""Tests for pipeline scheduler."""

from __future__ import annotations

from unittest.mock import MagicMock

from live_translator.pipeline.scheduler import PipelineScheduler, PipelineStatus


def test_pipeline_initial_state() -> None:
    """Pipeline should start in IDLE state."""
    pipeline = PipelineScheduler(MagicMock(), MagicMock(), MagicMock())
    assert pipeline.status == PipelineStatus.IDLE


def test_pipeline_start_transitions_to_streaming() -> None:
    """Starting the pipeline should transition to STREAMING."""
    pipeline = PipelineScheduler(MagicMock(), MagicMock(), MagicMock())
    pipeline.start()
    assert pipeline.status == PipelineStatus.STREAMING


def test_pipeline_stop_transitions_to_idle() -> None:
    """Stopping the pipeline should transition to IDLE."""
    pipeline = PipelineScheduler(MagicMock(), MagicMock(), MagicMock())
    pipeline.start()
    pipeline.stop()
    assert pipeline.status == PipelineStatus.IDLE


def test_pipeline_pause_resume() -> None:
    """Pipeline should support pause/resume."""
    pipeline = PipelineScheduler(MagicMock(), MagicMock(), MagicMock())
    pipeline.start()
    pipeline.pause()
    assert pipeline.status == PipelineStatus.PAUSED
    pipeline.resume()
    assert pipeline.status == PipelineStatus.STREAMING


def test_pipeline_start_calls_audio_source_and_asr() -> None:
    """Starting should begin audio capture and create ASR session."""
    audio_source = MagicMock()
    asr_service = MagicMock()
    asr_session = MagicMock()
    asr_service.create_session.return_value = asr_session

    pipeline = PipelineScheduler(audio_source, asr_service, MagicMock())
    pipeline.start()

    asr_service.create_session.assert_called_once()
    audio_source.start.assert_called_once()


def test_pipeline_forwards_translation() -> None:
    """Final ASR result should be translated and forwarded."""
    audio_source = MagicMock()
    translator = MagicMock()
    translator.translate.return_value = "你好"

    asr_session = MagicMock()
    asr_service = MagicMock()
    asr_service.create_session.return_value = asr_session

    pipeline = PipelineScheduler(audio_source, asr_service, translator)

    result: list[tuple[str, str]] = []
    pipeline.on_translation = lambda o, t: result.append((o, t))

    pipeline.start()

    # Simulate final callback
    pipeline._on_asr_final("Hello")

    translator.translate.assert_called_once_with(
        "Hello",
        source_lang="auto",
        target_lang="ZH",
    )
    assert result == [("Hello", "你好")]


def test_pipeline_partial_does_not_translate() -> None:
    """Partial ASR result should NOT trigger translation (sync mode)."""
    audio_source = MagicMock()
    translator = MagicMock()
    asr_session = MagicMock()
    asr_service = MagicMock()
    asr_service.create_session.return_value = asr_session

    pipeline = PipelineScheduler(audio_source, asr_service, translator)
    pipeline.start()

    pipeline._on_asr_partial("Hello par")

    translator.translate.assert_not_called()
