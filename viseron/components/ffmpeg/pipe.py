"""Lifecycle management for the FFmpeg subprocesses of a camera."""

from __future__ import annotations

import subprocess as sp
from typing import TYPE_CHECKING

from viseron.helpers.logs import LogPipe
from viseron.watchdog.subprocess_watchdog import RestartablePopen

if TYPE_CHECKING:
    import logging


class FFmpegPipe:
    """FFmpeg subprocesses for a camera."""

    def __init__(
        self,
        camera_identifier: str,
        logger: logging.Logger,
        loglevel: int,
        decoder_command: list[str] | None = None,
        segment_command: list[str] | None = None,
    ) -> None:
        self._camera_identifier = camera_identifier
        self._logger = logger
        self._loglevel = loglevel
        self._decoder_command = decoder_command
        self._segment_command = segment_command

        self._pipe: RestartablePopen | None = None
        self._log_pipe: LogPipe | None = None
        self.segment_process: RestartablePopen | None = None

    def _close_log_pipe(self) -> None:
        try:
            if self._log_pipe:
                self._log_pipe.close()
                self._log_pipe = None
        except OSError as error:
            self._logger.error("Failed to close log pipe: %s", error)

    def start(self) -> None:
        """Start the FFmpeg subprocesses.

        Called from inside the frame reader process, which is the only holder of
        a handle on these processes. start_new_session=False keeps them in the
        frame reader's process group so that killing it takes them with it.
        """
        self._close_log_pipe()
        self._log_pipe = LogPipe(self._logger, self._loglevel)

        if self._segment_command:
            self._logger.debug(
                f"FFmpeg segments command: {' '.join(self._segment_command)}"
            )
            self.segment_process = RestartablePopen(
                self._segment_command,
                name=f"viseron.camera.{self._camera_identifier}.segments",
                stdin=sp.DEVNULL,
                stdout=sp.PIPE,
                stderr=self._log_pipe,
                start_new_session=False,
            )

        if self._decoder_command:
            self._logger.debug(
                f"FFmpeg decoder command: {' '.join(self._decoder_command)}"
            )
            self._pipe = RestartablePopen(
                self._decoder_command,
                name=f"viseron.camera.{self._camera_identifier}.pipe",
                register=False,
                stdin=sp.DEVNULL,
                stdout=sp.PIPE,
                stderr=self._log_pipe,
                start_new_session=False,
            )

    def poll(self) -> int | None:
        """Poll the decoder subprocess."""
        if self._pipe:
            return self._pipe.poll()
        return None

    def read(self, frame_bytes_size: int) -> bytes | None:
        """Return a single frame from the decoder subprocess."""
        try:
            if self._pipe and self._pipe.stdout:
                return self._pipe.stdout.read(frame_bytes_size)
        except Exception:  # pylint: disable=broad-except
            self._logger.exception("Error reading frame from pipe")
        return None

    def _terminate(self, process: RestartablePopen, description: str) -> None:
        self._logger.debug(f"Terminating {description}")
        try:
            process.terminate()
            try:
                process.communicate(timeout=5)
            except sp.TimeoutExpired:
                self._logger.debug("FFmpeg did not terminate, killing instead.")
                process.kill()
                process.communicate()
        except (AttributeError, OSError) as error:
            self._logger.error(f"Failed to close {description}: {error}")

    def close(self) -> None:
        """Close the FFmpeg subprocesses."""
        self._logger.debug("Closing pipe")
        if self.segment_process:
            self._terminate(self.segment_process, "segment process")
        if self._pipe:
            self._terminate(self._pipe, "pipe")
        self._close_log_pipe()
