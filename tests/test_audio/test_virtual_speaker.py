"""Tests for VirtualSpeakerSource."""

from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import ANY, MagicMock, call, patch

import pytest

from live_translator.audio.source import AudioSource
from live_translator.audio.virtual_speaker import VirtualSpeakerSource


# ---------------------------------------------------------------------------
#  Protocol conformance
# ---------------------------------------------------------------------------

class TestProtocolConformance:
    """VirtualSpeakerSource must implement the AudioSource protocol."""

    def test_is_importable(self) -> None:
        assert VirtualSpeakerSource is not None

    def test_conforms_to_audio_source_protocol(self) -> None:
        src = VirtualSpeakerSource()
        assert isinstance(src, AudioSource)

    def test_has_required_attributes(self) -> None:
        src = VirtualSpeakerSource()
        assert hasattr(src, "sample_rate")
        assert hasattr(src, "channels")
        assert hasattr(src, "start")
        assert hasattr(src, "stop")
        assert hasattr(src, "is_capturing")


# ---------------------------------------------------------------------------
#  Constructor
# ---------------------------------------------------------------------------

class TestConstructor:
    """VirtualSpeakerSource constructor parameter handling."""

    def test_default_parameters(self) -> None:
        src = VirtualSpeakerSource()
        assert src.sink_name == "LiveTranslatorVirtualSpeaker"
        assert src.sink_description == "LiveTranslator Virtual Speaker"
        assert src.sample_rate == 16000
        assert src.channels == 1
        assert src.blocksize == 2048
        assert src.output_sink_name is None
        assert not src.is_capturing

    def test_custom_parameters(self) -> None:
        src = VirtualSpeakerSource(
            sink_name="CustomSink",
            sink_description="Custom Desc",
            sample_rate=44100,
            channels=2,
            blocksize=4096,
            output_sink_name="alsa_output.my_sink",
        )
        assert src.sink_name == "CustomSink"
        assert src.sink_description == "Custom Desc"
        assert src.sample_rate == 44100
        assert src.channels == 2
        assert src.blocksize == 4096
        assert src.output_sink_name == "alsa_output.my_sink"
        assert not src.is_capturing

    def test_output_sink_name_default_none(self) -> None:
        src = VirtualSpeakerSource()
        assert src.output_sink_name is None


# ---------------------------------------------------------------------------
#  list_sinks  (static)
# ---------------------------------------------------------------------------

class TestListSinks:
    """VirtualSpeakerSource.list_sinks() parses pactl output correctly."""

    def test_returns_empty_list_when_pactl_not_found(self) -> None:
        with patch.object(subprocess, "run", side_effect=FileNotFoundError):
            sinks = VirtualSpeakerSource.list_sinks()
        assert sinks == []

    def test_returns_empty_list_on_timeout(self) -> None:
        with patch.object(subprocess, "run", side_effect=subprocess.TimeoutExpired(cmd="pactl", timeout=10)):
            sinks = VirtualSpeakerSource.list_sinks()
        assert sinks == []

    def test_returns_empty_list_on_called_process_error(self) -> None:
        with patch.object(subprocess, "run", side_effect=subprocess.CalledProcessError(1, "pactl")):
            sinks = VirtualSpeakerSource.list_sinks()
        assert sinks == []

    def test_parses_single_sink(self) -> None:
        pactl_output = (
            "Sink #0\n"
            "\tState: RUNNING\n"
            "\tName: alsa_output.pci-0000_03_00.6.HiFi__Speaker__sink\n"
            "\tDescription: Ryzen HD Audio Controller Speaker\n"
            "\tDriver: PipeWire\n"
            "\n"
        )
        mock_run = MagicMock()
        mock_run.stdout = pactl_output
        with patch.object(subprocess, "run", return_value=mock_run):
            sinks = VirtualSpeakerSource.list_sinks()

        assert len(sinks) == 1
        assert sinks[0]["name"] == "alsa_output.pci-0000_03_00.6.HiFi__Speaker__sink"
        assert sinks[0]["description"] == "Ryzen HD Audio Controller Speaker"

    def test_parses_multiple_sinks(self) -> None:
        pactl_output = (
            "Sink #42\n"
            "\tName: sink_1\n"
            "\tDescription: First Sink\n"
            "\n"
            "Sink #43\n"
            "\tName: sink_2\n"
            "\tDescription: Second Sink\n"
            "\n"
        )
        mock_run = MagicMock()
        mock_run.stdout = pactl_output
        with patch.object(subprocess, "run", return_value=mock_run):
            sinks = VirtualSpeakerSource.list_sinks()

        assert len(sinks) == 2
        assert sinks[0]["name"] == "sink_1"
        assert sinks[0]["description"] == "First Sink"
        assert sinks[1]["name"] == "sink_2"
        assert sinks[1]["description"] == "Second Sink"

    def test_handles_empty_output(self) -> None:
        mock_run = MagicMock()
        mock_run.stdout = ""
        with patch.object(subprocess, "run", return_value=mock_run):
            sinks = VirtualSpeakerSource.list_sinks()
        assert sinks == []

    def test_handles_sink_without_description(self) -> None:
        pactl_output = (
            "Sink #0\n"
            "\tName: some_sink\n"
            "\n"
        )
        mock_run = MagicMock()
        mock_run.stdout = pactl_output
        with patch.object(subprocess, "run", return_value=mock_run):
            sinks = VirtualSpeakerSource.list_sinks()

        assert len(sinks) == 1
        assert sinks[0]["name"] == "some_sink"
        assert "description" not in sinks[0]


# ---------------------------------------------------------------------------
#  get_default_sink_name  (static)
# ---------------------------------------------------------------------------

class TestGetDefaultSinkName:
    """VirtualSpeakerSource.get_default_sink_name() behaviour."""

    def test_returns_none_when_pactl_not_found(self) -> None:
        with patch.object(subprocess, "run", side_effect=FileNotFoundError):
            result = VirtualSpeakerSource.get_default_sink_name()
        assert result is None

    def test_returns_none_on_error(self) -> None:
        with patch.object(subprocess, "run", side_effect=subprocess.CalledProcessError(1, "pactl")):
            result = VirtualSpeakerSource.get_default_sink_name()
        assert result is None

    def test_returns_sink_name(self) -> None:
        mock_run = MagicMock()
        mock_run.stdout = "alsa_output.pci-0000_03_00.6.HiFi__Speaker__sink\n"
        with patch.object(subprocess, "run", return_value=mock_run):
            result = VirtualSpeakerSource.get_default_sink_name()
        assert result == "alsa_output.pci-0000_03_00.6.HiFi__Speaker__sink"

    def test_trims_whitespace(self) -> None:
        mock_run = MagicMock()
        mock_run.stdout = "  my_sink  \n"
        with patch.object(subprocess, "run", return_value=mock_run):
            result = VirtualSpeakerSource.get_default_sink_name()
        assert result == "my_sink"


# ---------------------------------------------------------------------------
#  _create_virtual_sink  /  _destroy_virtual_sink
# ---------------------------------------------------------------------------

class TestVirtualSinkLifecycle:
    """Low-level sink creation and destruction."""

    def test_create_virtual_sink_success(self) -> None:
        src = VirtualSpeakerSource()
        mock_run = MagicMock()
        mock_run.stdout = "12345\n"

        # _cleanup_orphan_sink runs pactl list sinks short internally,
        # so we expect 2 pactl calls: list + load-module
        expected_calls = [
            call(
                ["pactl", "list", "sinks", "short"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            ),
            call(
                [
                    "pactl",
                    "load-module",
                    "module-null-sink",
                    "sink_name=LiveTranslatorVirtualSpeaker",
                    "sink_properties=device.description=LiveTranslator Virtual Speaker",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            ),
        ]

        with patch.object(subprocess, "run", return_value=mock_run) as mock:
            src._create_virtual_sink()

        assert src._null_sink_module_id == 12345
        mock.assert_has_calls(expected_calls)

    def test_create_virtual_sink_destroys_existing_first(self) -> None:
        src = VirtualSpeakerSource()
        src._null_sink_module_id = 99999

        mock_run = MagicMock()
        mock_run.stdout = "12345\n"

        with (
            patch.object(subprocess, "run", return_value=mock_run),
            patch.object(src, "_destroy_virtual_sink") as mock_destroy,
        ):
            src._create_virtual_sink()

        mock_destroy.assert_called_once()
        assert src._null_sink_module_id == 12345

    def test_create_virtual_sink_raises_on_non_numeric_output(self) -> None:
        src = VirtualSpeakerSource()
        mock_run = MagicMock()
        mock_run.stdout = "not a number\n"

        with patch.object(subprocess, "run", return_value=mock_run):
            with pytest.raises(RuntimeError, match="Unexpected pactl output"):
                src._create_virtual_sink()

    def test_create_virtual_sink_raises_on_pactl_missing(self) -> None:
        src = VirtualSpeakerSource()
        with patch.object(subprocess, "run", side_effect=FileNotFoundError):
            with pytest.raises(RuntimeError, match="pactl not found"):
                src._create_virtual_sink()

    def test_create_virtual_sink_raises_on_failure(self) -> None:
        src = VirtualSpeakerSource()
        exc = subprocess.CalledProcessError(1, "pactl", stderr="some error")
        with patch.object(subprocess, "run", side_effect=exc):
            with pytest.raises(RuntimeError, match="Failed to create"):
                src._create_virtual_sink()

    def test_destroy_virtual_sink_success(self) -> None:
        src = VirtualSpeakerSource()
        src._null_sink_module_id = 12345

        with patch.object(subprocess, "run") as mock:
            src._destroy_virtual_sink()

        assert src._null_sink_module_id is None
        mock.assert_called_once_with(
            ["pactl", "unload-module", "12345"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

    def test_destroy_virtual_sink_noop_when_no_module(self) -> None:
        """No module → no unload → just orphan check → one pactl call."""
        src = VirtualSpeakerSource()
        mock_run = MagicMock()
        mock_run.stdout = ""

        with patch.object(subprocess, "run", return_value=mock_run) as mock:
            src._destroy_virtual_sink()

        # _cleanup_orphan_sink calls "pactl list sinks short"
        # but no unload-module should happen
        unload_calls = [c for c in mock.call_args_list if "unload-module" in str(c)]
        assert len(unload_calls) == 0
        assert src._null_sink_module_id is None


# ---------------------------------------------------------------------------
#  Loopback management
# ---------------------------------------------------------------------------

class TestLoopbackLifecycle:
    """Loopback creation and destruction."""

    def test_create_loopback_success(self) -> None:
        src = VirtualSpeakerSource(sink_name="TestSink")
        mock_run = MagicMock()
        mock_run.stdout = "54321\n"

        with patch.object(subprocess, "run", return_value=mock_run) as mock:
            src._create_loopback("alsa_output.my_sink")

        assert src._loopback_module_id == 54321
        mock.assert_called_once_with(
            [
                "pactl",
                "load-module",
                "module-loopback",
                "source=TestSink.monitor",
                "sink=alsa_output.my_sink",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

    def test_create_loopback_raises_on_pactl_missing(self) -> None:
        src = VirtualSpeakerSource()
        with patch.object(subprocess, "run", side_effect=FileNotFoundError):
            with pytest.raises(RuntimeError, match="pactl not found"):
                src._create_loopback("some_sink")

    def test_create_loopback_raises_on_failure(self) -> None:
        src = VirtualSpeakerSource()
        exc = subprocess.CalledProcessError(1, "pactl", stderr="load failed")
        with patch.object(subprocess, "run", side_effect=exc):
            with pytest.raises(RuntimeError, match="Failed to create loopback"):
                src._create_loopback("some_sink")

    def test_destroy_loopback_success(self) -> None:
        src = VirtualSpeakerSource()
        src._loopback_module_id = 54321

        with patch.object(subprocess, "run") as mock:
            src._destroy_loopback()

        assert src._loopback_module_id is None
        mock.assert_called_once_with(
            ["pactl", "unload-module", "54321"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

    def test_destroy_loopback_noop_when_no_module(self) -> None:
        src = VirtualSpeakerSource()
        with patch.object(subprocess, "run") as mock:
            src._destroy_loopback()
        mock.assert_not_called()


# ---------------------------------------------------------------------------
#  _verify_monitor_source
# ---------------------------------------------------------------------------

class TestVerifyMonitorSource:
    """Monitor source verification."""

    def test_passes_when_source_found(self) -> None:
        src = VirtualSpeakerSource(sink_name="TestSink")
        mock_run = MagicMock()
        mock_run.stdout = (
            "42\tTestSink.monitor\tPipeWire\ts32le 2ch 48000Hz\tRUNNING\n"
        )
        with patch.object(subprocess, "run", return_value=mock_run):
            src._verify_monitor_source("TestSink.monitor")

    def test_raises_when_source_not_found(self) -> None:
        src = VirtualSpeakerSource(sink_name="TestSink")
        mock_run = MagicMock()
        mock_run.stdout = (
            "53\talsa_input.something\tPipeWire\ts32le 2ch 48000Hz\tRUNNING\n"
        )
        with patch.object(subprocess, "run", return_value=mock_run):
            with pytest.raises(RuntimeError, match="Monitor source.*not found"):
                src._verify_monitor_source("TestSink.monitor")


# ---------------------------------------------------------------------------
#  start / stop orchestration
# ---------------------------------------------------------------------------

class TestStartStop:
    """High-level start/stop integration with mocks."""

    def test_start_creates_sink_and_loopback_and_parec(self) -> None:
        src = VirtualSpeakerSource(output_sink_name="physical_sink")

        with (
            patch.object(src, "_create_virtual_sink") as mock_create_sink,
            patch.object(src, "_verify_monitor_source") as mock_verify,
            patch.object(src, "_create_loopback") as mock_create_loop,
            patch.object(src, "_start_parec") as mock_start_parec,
        ):
            src.start(lambda x: None)

        mock_create_sink.assert_called_once()
        mock_verify.assert_called_once_with("LiveTranslatorVirtualSpeaker.monitor")
        mock_create_loop.assert_called_once_with("physical_sink")
        mock_start_parec.assert_called_once_with("LiveTranslatorVirtualSpeaker.monitor")
        assert src.is_capturing

    def test_start_no_loopback_when_output_none(self) -> None:
        src = VirtualSpeakerSource(output_sink_name=None)

        with (
            patch.object(src, "_create_virtual_sink"),
            patch.object(src, "_verify_monitor_source"),
            patch.object(src, "_create_loopback") as mock_create_loop,
            patch.object(src, "_start_parec"),
        ):
            src.start(lambda x: None)

        mock_create_loop.assert_not_called()
        assert src.is_capturing

    def test_start_ignored_when_already_capturing(self) -> None:
        src = VirtualSpeakerSource()
        src._capturing = True

        with (
            patch.object(src, "_create_virtual_sink") as mock_create,
            patch.object(src, "_start_parec") as mock_parec,
        ):
            src.start(lambda x: None)

        mock_create.assert_not_called()
        mock_parec.assert_not_called()

    def test_stop_destroys_everything(self) -> None:
        src = VirtualSpeakerSource()
        src._capturing = True
        src._callback = lambda x: None

        with (
            patch.object(src, "_stop_parec") as mock_stop_parec,
            patch.object(src, "_destroy_loopback") as mock_destroy_loop,
            patch.object(src, "_destroy_virtual_sink") as mock_destroy_sink,
        ):
            src.stop()

        mock_stop_parec.assert_called_once()
        mock_destroy_loop.assert_called_once()
        mock_destroy_sink.assert_called_once()
        assert not src.is_capturing
        assert src._callback is None

    def test_stop_noop_when_not_capturing(self) -> None:
        src = VirtualSpeakerSource()

        with (
            patch.object(src, "_stop_parec") as mock_stop,
            patch.object(src, "_destroy_loopback") as mock_loop,
            patch.object(src, "_destroy_virtual_sink") as mock_sink,
        ):
            src.stop()

        mock_stop.assert_not_called()
        mock_loop.assert_not_called()
        mock_sink.assert_not_called()


# ---------------------------------------------------------------------------
#  Context manager
# ---------------------------------------------------------------------------

class TestContextManager:
    """Context manager protocol."""

    def test_enter_returns_self(self) -> None:
        src = VirtualSpeakerSource()
        with src as s:
            assert s is src

    def test_exit_calls_stop(self) -> None:
        src = VirtualSpeakerSource()
        with patch.object(src, "stop") as mock_stop:
            with src:
                pass
        mock_stop.assert_called_once()


# ---------------------------------------------------------------------------
#  _cleanup_orphan_sink
# ---------------------------------------------------------------------------

class TestCleanupOrphanSink:
    """Orphan sink cleanup."""

    def test_removes_orphan_sink(self) -> None:
        """If a sink with our name exists, unload its module."""
        src = VirtualSpeakerSource(sink_name="TestSink")
        mock_run = MagicMock()
        # pactl list sinks short format:
        # <id>\t<name>\t<driver>\t<state>\t<module_id>
        mock_run.stdout = (
            "52\talsa_output.default\tPipeWire\tRUNNING\t1\n"
            "99\tTestSink\tPipeWire\tSUSPENDED\t42\n"
        )

        with patch.object(subprocess, "run", return_value=mock_run) as mock:
            src._cleanup_orphan_sink()

        # Should unload module 42
        unload_call = [c for c in mock.call_args_list if "unload-module" in str(c)]
        assert len(unload_call) == 1
        assert "42" in str(unload_call[0])

    def test_noop_when_no_orphan(self) -> None:
        src = VirtualSpeakerSource(sink_name="TestSink")
        mock_run = MagicMock()
        mock_run.stdout = (
            "52\talsa_output.default\tPipeWire\tRUNNING\t1\n"
        )

        with patch.object(subprocess, "run", return_value=mock_run) as mock:
            src._cleanup_orphan_sink()

        unload_calls = [c for c in mock.call_args_list if "unload-module" in str(c)]
        assert len(unload_calls) == 0
