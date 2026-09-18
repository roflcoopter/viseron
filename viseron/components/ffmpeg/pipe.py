"""Lifecycle management for the FFmpeg subprocesses of a camera."""

from __future__ import annotations

import os
import subprocess as sp
from typing import TYPE_CHECKING, BinaryIO

from viseron.helpers.logs import LogPipe
from viseron.watchdog.subprocess_watchdog import RestartablePopen

from .const import ORIN_RAWVIDEO_OUTPUT

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
        dedicated_rawvideo_fd: bool = False,
    ) -> None:
        self._camera_identifier = camera_identifier
        self._logger = logger
        self._loglevel = loglevel
        self._decoder_command = decoder_command
        self._segment_command = segment_command
        self._dedicated_rawvideo_fd = dedicated_rawvideo_fd

        self._pipe: RestartablePopen | None = None
        self._log_pipe: LogPipe | None = None
        self._stdout_log_pipe: LogPipe | None = None
        self._rawvideo_pipe: BinaryIO | None = None
        self.segment_process: RestartablePopen | None = None

    def _close_log_pipe(self) -> None:
        for attribute in ("_stdout_log_pipe", "_log_pipe"):
            log_pipe = getattr(self, attribute)
            if log_pipe:
                try:
                    log_pipe.close()
                    if self._dedicated_rawvideo_fd:
                        log_pipe.join(timeout=1)
                except OSError as error:
                    self._logger.error("Failed to close log pipe: %s", error)
                setattr(self, attribute, None)

    def _close_rawvideo_pipe(self) -> None:
        if self._rawvideo_pipe:
            try:
                self._rawvideo_pipe.close()
            except OSError as error:
                self._logger.error("Failed to close rawvideo pipe: %s", error)
            self._rawvideo_pipe = None

    def _start_decoder_with_rawvideo_fd(self) -> None:
        """Create the pipe here; the forkserver payload contains no live FD."""
        if (
            not self._decoder_command
            or self._decoder_command[-1] != ORIN_RAWVIDEO_OUTPUT
        ):
            raise RuntimeError(
                "Orin decoder command must end with rawvideo output token"
            )

        read_fd, write_fd = os.pipe()
        process: RestartablePopen | None = None
        try:
            self._rawvideo_pipe = os.fdopen(read_fd, "rb", buffering=0)
            read_fd = -1
            self._stdout_log_pipe = LogPipe(self._logger, self._loglevel)
            command = [*self._decoder_command[:-1], f"pipe:{write_fd}"]
            self._logger.debug("FFmpeg decoder command: %s", " ".join(command))
            process = RestartablePopen(
                command,
                name=f"viseron.camera.{self._camera_identifier}.pipe",
                register=False,
                stdin=sp.DEVNULL,
                stdout=self._stdout_log_pipe,
                stderr=self._log_pipe,
                pass_fds=(write_fd,),
                start_new_session=False,
            )
            self._pipe = process
        finally:
            # Only FFmpeg keeps a write end after successful spawn, so EOF is visible.
            os.close(write_fd)
            if read_fd >= 0:
                os.close(read_fd)
            if process is None:
                self._close_rawvideo_pipe()

    def start(self) -> None:
        """Start the FFmpeg subprocesses.

        Called from inside the frame reader process, which is the only holder of
        a handle on these processes. start_new_session=False keeps them in the
        frame reader's process group so that killing it takes them with it.
        """
        self._close_rawvideo_pipe()
        self._close_log_pipe()
        try:
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
                if self._dedicated_rawvideo_fd:
                    self._start_decoder_with_rawvideo_fd()
                else:
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
        except Exception:
            # A segment may already be running when decoder startup fails.
            if self._dedicated_rawvideo_fd:
                self.close()
            raise

    def poll(self) -> int | None:
        """Poll the decoder subprocess."""
        if self._pipe:
            return self._pipe.poll()
        return None

    def read(self, frame_bytes_size: int) -> bytes | None:
        """Return a single frame from the decoder subprocess."""
        try:
            if self._dedicated_rawvideo_fd:
                if not self._rawvideo_pipe:
                    return None
                frame = bytearray()
                while len(frame) < frame_bytes_size:
                    chunk = self._rawvideo_pipe.read(frame_bytes_size - len(frame))
                    if not chunk:
                        if frame:
                            self._logger.error(
                                "Partial rawvideo frame at EOF: "
                                "expected %s bytes, got %s",
                                frame_bytes_size,
                                len(frame),
                            )
                        return None
                    frame.extend(chunk)
                return bytes(frame)
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
            if self._dedicated_rawvideo_fd:
                self.segment_process = None
        if self._pipe:
            self._terminate(self._pipe, "pipe")
            if self._dedicated_rawvideo_fd:
                self._pipe = None
        self._close_rawvideo_pipe()
        self._close_log_pipe()
