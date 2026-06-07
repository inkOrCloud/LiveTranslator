"""Virtual speaker audio source using PulseAudio null-sink and ``parec``.

Creates a virtual PulseAudio sink (``module-null-sink``) and captures audio
from its monitor source using ``parec`` (PulseAudio recorder). This provides
a dedicated capture target that does not interfere with normal audio output.

Optionally creates a ``module-loopback`` to copy audio from the virtual sink
to a physical output sink, so the user can still hear audio.

Requires:
    - PulseAudio or PipeWire (with PulseAudio compatibility)
    - ``pactl`` and ``parec`` command-line tools in ``$PATH``
"""

from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import Callable
from threading import Event, Thread
from typing import Any

logger = logging.getLogger(__name__)

# Default virtual sink name
DEFAULT_SINK_NAME = "LiveTranslatorVirtualSpeaker"
DEFAULT_SINK_DESCRIPTION = "LiveTranslator Virtual Speaker"

# PCM16 parameters for ``parec``
_PAREC_FORMAT = "s16ne"  # native-endian 16-bit PCM


class VirtualSpeakerSource:
    """Captures system audio by creating a virtual PulseAudio speaker.

    On :meth:`start`, a PulseAudio null-sink is created and ``parec`` is
    launched to capture from its monitor source as raw PCM16 audio.

    If *output_sink_name* is provided, a ``module-loopback`` is also created
    so audio played through the virtual sink is forwarded to a physical sink.

    The virtual sink, loopback, and ``parec`` process are cleaned up on
    :meth:`stop`.
    """

    def __init__(
        self,
        sink_name: str = DEFAULT_SINK_NAME,
        sink_description: str = DEFAULT_SINK_DESCRIPTION,
        sample_rate: int = 16000,
        channels: int = 1,
        blocksize: int = 2048,
        output_sink_name: str | None = None,
    ) -> None:
        """Initialize the virtual speaker source.

        Args:
            sink_name: PulseAudio sink name for the virtual speaker.
            sink_description: Human-readable description.
            sample_rate: Target sample rate in Hz (default: 16000).
            channels: Number of channels (default: 1 for mono).
            blocksize: Audio buffer block size (default: 2048).
            output_sink_name: Physical sink name to loop audio to, or
                ``None`` for no audio output.
        """
        self.sink_name = sink_name
        self.sink_description = sink_description
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize
        self.output_sink_name = output_sink_name

        self._parec_process: subprocess.Popen[bytes] | None = None
        self._parec_thread: Thread | None = None
        self._stop_event = Event()
        self._callback: Callable[[bytes], None] | None = None
        self._null_sink_module_id: int | None = None
        self._loopback_module_id: int | None = None
        self._capturing = False

        logger.debug(
            "VirtualSpeakerSource initialized: sink=%s, rate=%d, channels=%d, "
            "blocksize=%d, output_sink=%s",
            sink_name,
            sample_rate,
            channels,
            blocksize,
            output_sink_name or "(none)",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, callback: Callable[[bytes], None]) -> None:
        """Create the virtual speaker and start capturing its audio with ``parec``.

        Args:
            callback: Called with PCM16 mono audio chunks.
        """
        if self._capturing:
            logger.warning("VirtualSpeakerSource already capturing, ignoring start")
            return

        self._callback = callback
        self._stop_event.clear()

        # Create the null-sink
        self._create_virtual_sink()

        monitor_source = f"{self.sink_name}.monitor"

        # Verify the monitor source exists
        self._verify_monitor_source(monitor_source)

        # Optionally create loopback to a physical sink
        if self.output_sink_name:
            self._create_loopback(self.output_sink_name)

        # Launch parec to capture from the monitor source
        self._start_parec(monitor_source)

        self._capturing = True
        logger.info(
            "Virtual speaker capture started: source=%s, rate=%d, channels=%d, "
            "output_sink=%s",
            monitor_source,
            self.sample_rate,
            self.channels,
            self.output_sink_name or "(none)",
        )

    def stop(self) -> None:
        """Stop capturing and destroy the virtual speaker."""
        if not self._capturing:
            logger.debug("VirtualSpeakerSource not capturing, ignoring stop")
            return

        self._capturing = False
        self._callback = None

        # Stop parec
        self._stop_parec()

        # Destroy loopback first (must happen before destroying the sink)
        self._destroy_loopback()

        # Destroy the virtual sink
        self._destroy_virtual_sink()

        logger.debug("Virtual speaker capture stopped and sink destroyed")

    @property
    def is_capturing(self) -> bool:
        """Whether the source is currently capturing."""
        return self._capturing

    # ------------------------------------------------------------------
    # PulseAudio sink listing (for GUI)
    # ------------------------------------------------------------------

    @staticmethod
    def list_sinks() -> list[dict[str, str]]:
        """List available physical PulseAudio sinks.

        Returns:
            List of dicts with ``"name"`` and ``"description"`` keys for
            each non-virtual sink.
        """
        sinks: list[dict[str, str]] = []
        try:
            result = subprocess.run(
                ["pactl", "list", "sinks"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            logger.warning("Failed to list PulseAudio sinks: %s", exc)
            return sinks

        current: dict[str, str] = {}
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("Name:"):
                current["name"] = stripped.split("Name:", 1)[1].strip()
            elif stripped.startswith("Description:"):
                current["description"] = stripped.split("Description:", 1)[1].strip()
            elif stripped == "" and "name" in current:
                sinks.append(current)
                current = {}

        if "name" in current:
            sinks.append(current)

        return sinks

    @staticmethod
    def get_default_sink_name() -> str | None:
        """Get the default PulseAudio output sink name.

        Returns:
            Sink name string, or ``None`` on failure.
        """
        try:
            result = subprocess.run(
                ["pactl", "get-default-sink"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            name = result.stdout.strip()
            return name if name else None
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            logger.warning("Failed to get default sink: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Virtual sink management
    # ------------------------------------------------------------------

    def _create_virtual_sink(self) -> None:
        """Create a PulseAudio null-sink (virtual speaker).

        Raises:
            RuntimeError: If the sink could not be created.
        """
        # Clean up any stale sink first
        self._destroy_virtual_sink()

        logger.info(
            "Creating virtual PulseAudio sink: name=%s, description=%s",
            self.sink_name,
            self.sink_description,
        )

        try:
            result = subprocess.run(
                [
                    "pactl",
                    "load-module",
                    "module-null-sink",
                    f"sink_name={self.sink_name}",
                    f"sink_properties=device.description={self.sink_description}",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            module_id_str = result.stdout.strip()
            if not module_id_str.isdigit():
                msg = f"Unexpected pactl output: '{module_id_str}'"
                logger.error(msg)
                raise RuntimeError(msg)

            self._null_sink_module_id = int(module_id_str)
            logger.info(
                "Virtual speaker created: sink=%s, module_id=%d",
                self.sink_name,
                self._null_sink_module_id,
            )

            # Give PulseAudio a moment to register
            time.sleep(0.3)

        except FileNotFoundError:
            msg = "pactl not found. PulseAudio or PipeWire is required."
            logger.error(msg)
            raise RuntimeError(msg) from None
        except subprocess.TimeoutExpired:
            msg = "Timed out creating virtual PulseAudio sink."
            logger.error(msg)
            raise RuntimeError(msg) from None
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() if exc.stderr else ""
            msg = (
                f"Failed to create virtual PulseAudio sink "
                f"(exit code {exc.returncode}): {stderr}"
            )
            logger.error(msg)
            raise RuntimeError(msg) from None

    def _destroy_virtual_sink(self) -> None:
        """Destroy the virtual PulseAudio sink if it exists."""
        if self._null_sink_module_id is not None:
            logger.info(
                "Destroying virtual sink: module_id=%d, name=%s",
                self._null_sink_module_id,
                self.sink_name,
            )
            try:
                subprocess.run(
                    ["pactl", "unload-module", str(self._null_sink_module_id)],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=10,
                )
                logger.info("Virtual sink destroyed: module_id=%d", self._null_sink_module_id)
            except subprocess.TimeoutExpired:
                logger.warning("Timed out destroying virtual sink module %d", self._null_sink_module_id)
            except subprocess.CalledProcessError as exc:
                logger.warning(
                    "Failed to destroy virtual sink module %d: %s",
                    self._null_sink_module_id,
                    exc.stderr.strip(),
                )
            except FileNotFoundError:
                logger.warning("pactl not found, cannot destroy virtual sink")
            finally:
                self._null_sink_module_id = None
        else:
            self._cleanup_orphan_sink()

    def _cleanup_orphan_sink(self) -> None:
        """Remove any existing sink with our name (left over from crashes)."""
        logger.debug("Checking for orphan sink '%s'", self.sink_name)
        try:
            result = subprocess.run(
                ["pactl", "list", "sinks", "short"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            for line in result.stdout.strip().splitlines():
                if self.sink_name in line:
                    parts = line.split("\t")
                    if len(parts) >= 5 and parts[4].strip().isdigit():
                        mod_id = int(parts[4].strip())
                        logger.warning(
                            "Found orphan sink '%s' (module %d), removing",
                            self.sink_name,
                            mod_id,
                        )
                        subprocess.run(
                            ["pactl", "unload-module", str(mod_id)],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                    break
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass

    # ------------------------------------------------------------------
    # Loopback management
    # ------------------------------------------------------------------

    def _create_loopback(self, target_sink_name: str) -> None:
        """Create a ``module-loopback`` from the virtual sink to a physical sink.

        Args:
            target_sink_name: Name of the physical sink to forward audio to.

        Raises:
            RuntimeError: If the loopback could not be created.
        """
        logger.info(
            "Creating loopback: source=%s.monitor -> sink=%s",
            self.sink_name,
            target_sink_name,
        )

        try:
            result = subprocess.run(
                [
                    "pactl",
                    "load-module",
                    "module-loopback",
                    f"source={self.sink_name}.monitor",
                    f"sink={target_sink_name}",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            module_id_str = result.stdout.strip()
            if not module_id_str.isdigit():
                msg = f"Unexpected pactl output for loopback: '{module_id_str}'"
                logger.error(msg)
                raise RuntimeError(msg)

            self._loopback_module_id = int(module_id_str)
            logger.info(
                "Loopback created: module_id=%d, target=%s",
                self._loopback_module_id,
                target_sink_name,
            )

        except FileNotFoundError:
            msg = "pactl not found. PulseAudio or PipeWire is required."
            logger.error(msg)
            raise RuntimeError(msg) from None
        except subprocess.TimeoutExpired:
            msg = "Timed out creating loopback."
            logger.error(msg)
            raise RuntimeError(msg) from None
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() if exc.stderr else ""
            msg = (
                f"Failed to create loopback to '{target_sink_name}' "
                f"(exit code {exc.returncode}): {stderr}"
            )
            logger.error(msg)
            raise RuntimeError(msg) from None

    def _destroy_loopback(self) -> None:
        """Destroy the loopback module if it exists."""
        if self._loopback_module_id is not None:
            logger.info(
                "Destroying loopback: module_id=%d",
                self._loopback_module_id,
            )
            try:
                subprocess.run(
                    ["pactl", "unload-module", str(self._loopback_module_id)],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=10,
                )
                logger.info("Loopback destroyed: module_id=%d", self._loopback_module_id)
            except subprocess.TimeoutExpired:
                logger.warning("Timed out destroying loopback module %d", self._loopback_module_id)
            except subprocess.CalledProcessError as exc:
                logger.warning(
                    "Failed to destroy loopback module %d: %s",
                    self._loopback_module_id,
                    exc.stderr.strip(),
                )
            except FileNotFoundError:
                logger.warning("pactl not found, cannot destroy loopback")
            finally:
                self._loopback_module_id = None

    def _verify_monitor_source(self, monitor_source: str) -> None:
        """Verify that the monitor source exists in PulseAudio.

        Args:
            monitor_source: The monitor source name (``<sink>.monitor``).

        Raises:
            RuntimeError: If the monitor source is not found.
        """
        try:
            result = subprocess.run(
                ["pactl", "list", "sources", "short"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            for line in result.stdout.strip().splitlines():
                if monitor_source in line:
                    logger.info("Monitor source verified: %s", line.strip())
                    return

            msg = f"Monitor source '{monitor_source}' not found after creating sink"
            logger.error(msg)
            raise RuntimeError(msg)

        except FileNotFoundError:
            msg = "pactl not found"
            logger.error(msg)
            raise RuntimeError(msg) from None
        except subprocess.TimeoutExpired:
            msg = "Timed out listing PulseAudio sources"
            logger.error(msg)
            raise RuntimeError(msg) from None
        except subprocess.CalledProcessError as exc:
            msg = f"Failed to list PulseAudio sources: {exc.stderr.strip()}"
            logger.error(msg)
            raise RuntimeError(msg) from None

    # ------------------------------------------------------------------
    # parec capture
    # ------------------------------------------------------------------

    def _start_parec(self, monitor_source: str) -> None:
        """Launch ``parec`` to capture audio from the monitor source.

        Args:
            monitor_source: PulseAudio monitor source name.
        """
        cmd = [
            "parec",
            "--raw",
            f"--format={_PAREC_FORMAT}",
            f"--rate={self.sample_rate}",
            f"--channels={self.channels}",
            f"--device={monitor_source}",
        ]

        logger.info("Starting parec: %s", " ".join(cmd))

        try:
            self._parec_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            msg = "parec not found. PulseAudio/PipeWire utilities are required."
            logger.error(msg)
            self._destroy_loopback()
            self._destroy_virtual_sink()
            raise RuntimeError(msg) from None

        # Start a reader thread to consume stdout
        self._parec_thread = Thread(
            target=self._parec_reader,
            name="parec-reader",
            daemon=True,
        )
        self._parec_thread.start()

        # Brief check that the process is running
        time.sleep(0.2)
        if self._parec_process.poll() is not None:
            stderr_output = (
                self._parec_process.stderr.read().decode()
                if self._parec_process.stderr
                else ""
            )
            logger.error(
                "parec exited early (code %d): %s",
                self._parec_process.returncode,
                stderr_output,
            )
            self._destroy_loopback()
            self._destroy_virtual_sink()
            raise RuntimeError(
                f"parec failed to start (exit {self._parec_process.returncode}): "
                f"{stderr_output}"
            )

    def _parec_reader(self) -> None:
        """Read raw PCM16 data from parec stdout and deliver to the callback."""
        process = self._parec_process
        if process is None or process.stdout is None:
            logger.error("parec_reader: no process or stdout")
            return

        logger.debug("parec reader thread started")
        try:
            while not self._stop_event.is_set():
                # 2 bytes per sample
                chunk = process.stdout.read(self.blocksize * self.channels * 2)
                if not chunk:
                    logger.debug("parec stdout ended (EOF)")
                    break

                if self._callback and len(chunk) > 0:
                    self._callback(chunk)

        except Exception:
            logger.exception("Error in parec reader thread")
        finally:
            logger.debug("parec reader thread exiting")

    def _stop_parec(self) -> None:
        """Stop the parec process."""
        self._stop_event.set()

        if self._parec_process is not None:
            logger.debug("Terminating parec (PID %d)", self._parec_process.pid)
            try:
                self._parec_process.terminate()
                self._parec_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("parec did not terminate in time, killing")
                try:
                    self._parec_process.kill()
                    self._parec_process.wait(timeout=3)
                except Exception:
                    logger.exception("Failed to kill parec")
            except Exception:
                logger.exception("Error stopping parec")
            finally:
                self._parec_process = None

        # Wait for the reader thread to finish
        if self._parec_thread is not None and self._parec_thread.is_alive():
            self._parec_thread.join(timeout=3)
        self._parec_thread = None

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> VirtualSpeakerSource:
        """Context manager entry (does not auto-start)."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Context manager exit: ensures cleanup."""
        self.stop()
