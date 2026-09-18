"""Orin rawvideo transport on the current FFmpegPipe architecture."""

from __future__ import annotations

import logging
import multiprocessing as mp
import os
import pickle
import sys
from unittest.mock import MagicMock, patch

import pytest

from viseron.components.ffmpeg.const import (
    CONFIG_CODEC,
    CONFIG_FFMPEG_RECOVERABLE_ERRORS,
    CONFIG_PIX_FMT,
    CONFIG_RAW_COMMAND,
    CONFIG_STREAM_FORMAT,
    CONFIG_SUBSTREAM,
    DEFAULT_CODEC,
    FFMPEG_BACKEND_JETSON_ORIN_R39,
    ORIN_RAWVIDEO_OUTPUT,
)
from viseron.components.ffmpeg.frame_reader import FrameReaderConfig, run_frame_reader
from viseron.components.ffmpeg.pipe import FFmpegPipe
from viseron.components.ffmpeg.stream import (
    Stream,
    StreamInformation,
    validate_jetson_orin_r39_ffmpeg,
)
from viseron.const import ENV_FFMPEG_BACKEND, ENV_JETSON_NANO, ENV_RASPBERRYPI3

LOGGER = logging.getLogger(__name__)


def _stream(orin: bool) -> Stream:
    stream = Stream.__new__(Stream)
    stream._ffmpeg_backend = FFMPEG_BACKEND_JETSON_ORIN_R39 if orin else None
    stream.pixel_format = "nv12"
    return stream


def _decoder_command(*, partial: bool = False) -> list[str]:
    script = (
        "import os,sys,time; fd=int(sys.argv[1].split(':')[1]); "
        "os.write(1,b'diagnostic on stdout\\n'); "
        "os.write(fd,b'ab'); time.sleep(.03); "
        + ("os.write(fd,b'c'); " if partial else "os.write(fd,b'cdef'); ")
    )
    return [sys.executable, "-c", script, ORIN_RAWVIDEO_OUTPUT]


def _fd_count() -> int:
    return len(os.listdir("/proc/self/fd"))


def test_explicit_selection_and_legacy_decoder(monkeypatch: pytest.MonkeyPatch) -> None:
    """Platform detection alone does not select the dedicated transport."""
    monkeypatch.setenv(ENV_JETSON_NANO, "true")
    monkeypatch.delenv(ENV_FFMPEG_BACKEND, raising=False)
    ordinary = _stream(False)
    config = {CONFIG_CODEC: DEFAULT_CODEC, CONFIG_STREAM_FORMAT: "rtsp"}
    assert ordinary.output_args[-1] == "pipe:1"
    assert ordinary.get_decoder_codec(config, "h264") == ["-c:v", "h264_nvv4l2dec"]
    assert _stream(True).output_args[-1] == ORIN_RAWVIDEO_OUTPUT
    monkeypatch.delenv(ENV_JETSON_NANO)
    assert not ordinary.get_decoder_codec(config, "h264")
    assert _stream(True).get_decoder_codec(config, "h264") == ["-c:v", "h264_nvv4l2dec"]
    monkeypatch.setenv(ENV_RASPBERRYPI3, "true")
    assert _stream(True).get_decoder_codec(config, "h264") == ["-c:v", "h264_nvv4l2dec"]


def test_stream_selects_orin_only_with_explicit_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stream construction validates only when the backend is named."""
    config = {
        CONFIG_FFMPEG_RECOVERABLE_ERRORS: [],
        CONFIG_SUBSTREAM: None,
        CONFIG_PIX_FMT: "nv12",
    }
    information = StreamInformation(4, 4, 10, "h264", None, "url", config)
    monkeypatch.setenv(ENV_JETSON_NANO, "true")
    monkeypatch.setenv("VISERON_FFMPEG_PATH", "/fake/ffmpeg")
    with (
        patch("viseron.components.ffmpeg.stream.FFprobe"),
        patch.object(Stream, "get_stream_information", return_value=information),
        patch.object(Stream, "create_symlink"),
        patch(
            "viseron.components.ffmpeg.stream.validate_jetson_orin_r39_ffmpeg"
        ) as validate,
    ):
        monkeypatch.delenv(ENV_FFMPEG_BACKEND, raising=False)
        assert not Stream(config, MagicMock(), "cam").use_rawvideo_fd
        validate.assert_not_called()
        monkeypatch.setenv(ENV_FFMPEG_BACKEND, FFMPEG_BACKEND_JETSON_ORIN_R39)
        assert Stream(config, MagicMock(), "cam").use_rawvideo_fd
        validate.assert_called_once_with("/fake/ffmpeg")


def test_orin_raw_command_rejected_without_rewriting() -> None:
    """A user supplied command has no public dynamic FD contract."""
    stream = _stream(True)
    stream._substream = None
    stream._config = {CONFIG_RAW_COMMAND: "ffmpeg -f rawvideo pipe:1"}
    with pytest.raises(RuntimeError, match="raw_command is unsupported"):
        stream.build_command()


def test_capability_validation_accepts_decoders_and_nv12() -> None:
    """Orin selection requires both NVIDIA decoders to expose NV12."""
    validate_jetson_orin_r39_ffmpeg.cache_clear()
    results = [
        MagicMock(returncode=0, stdout="h264_nvv4l2dec hevc_nvv4l2dec", stderr=""),
        MagicMock(returncode=0, stdout="Supported pixel formats: nv12", stderr=""),
        MagicMock(returncode=0, stdout="Supported pixel formats: nv12", stderr=""),
    ]
    with patch("viseron.components.ffmpeg.stream.sp.run", side_effect=results) as run:
        validate_jetson_orin_r39_ffmpeg("/fake/ffmpeg")
    assert run.call_count == 3
    validate_jetson_orin_r39_ffmpeg.cache_clear()


def test_capability_validation_rejects_missing_output() -> None:
    """A decoder lacking NV12 cannot satisfy the Orin backend."""
    validate_jetson_orin_r39_ffmpeg.cache_clear()
    results = [
        MagicMock(returncode=0, stdout="h264_nvv4l2dec hevc_nvv4l2dec", stderr=""),
        MagicMock(returncode=0, stdout="Supported pixel formats: yuv420p", stderr=""),
        MagicMock(returncode=0, stdout="Supported pixel formats: nv12", stderr=""),
    ]
    with (
        patch("viseron.components.ffmpeg.stream.sp.run", side_effect=results),
        pytest.raises(RuntimeError, match="lacks NV12"),
    ):
        validate_jetson_orin_r39_ffmpeg("/fake/ffmpeg")
    validate_jetson_orin_r39_ffmpeg.cache_clear()


@pytest.mark.parametrize(
    ("fragments", "expected"),
    [
        ([b"abcdef"], b"abcdef"),
        ([b"a", b"bc", b"def"], b"abcdef"),
        ([b""], None),
        ([b"abc", b""], None),
    ],
)
def test_exact_frame_reads(fragments: list[bytes], expected: bytes | None) -> None:
    """Complete frames survive fragmentation; EOF never publishes a partial frame."""
    reader = MagicMock()
    reader.read.side_effect = fragments
    pipe = FFmpegPipe("cam", LOGGER, 10, dedicated_rawvideo_fd=True)
    pipe._rawvideo_pipe = reader
    assert pipe.read(6) == expected


def test_read_failure_and_abnormal_exit() -> None:
    """A read error yields no frame and the child exit remains observable."""
    pipe = FFmpegPipe("cam", LOGGER, 10, dedicated_rawvideo_fd=True)
    pipe._rawvideo_pipe = MagicMock()
    pipe._rawvideo_pipe.read.side_effect = OSError("broken")
    pipe._pipe = MagicMock()
    pipe._pipe.poll.return_value = 17
    assert pipe.read(6) is None
    assert pipe.poll() == 17


def test_real_decoder_stdout_isolation_restart_and_fd_cleanup(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Real child writes diagnostics to stdout and fragmented frames to its FD."""
    caplog.set_level(logging.INFO, logger=LOGGER.name)
    before = _fd_count()
    pipe = FFmpegPipe(
        "cam", LOGGER, logging.INFO, _decoder_command(), dedicated_rawvideo_fd=True
    )
    fds = []
    for _ in range(3):
        pipe.start()
        assert pipe._rawvideo_pipe is not None
        fds.append(pipe._rawvideo_pipe.fileno())
        assert pipe._pipe is not None
        pid = pipe._pipe.pid
        assert pipe.read(6) == b"abcdef"
        assert pipe.read(6) is None
        pipe.close()
        assert _fd_count() == before
        with pytest.raises(ChildProcessError):
            os.waitpid(pid, os.WNOHANG)
    assert len(fds) == 3  # Each start installed a new pipe, even if OS numbers recur.
    assert any("diagnostic on stdout" in record.message for record in caplog.records)


def test_partial_frame_real_child_and_exit() -> None:
    """A child exiting mid-frame returns EOF without exposing partial bytes."""
    pipe = FFmpegPipe(
        "cam",
        LOGGER,
        logging.INFO,
        _decoder_command(partial=True),
        dedicated_rawvideo_fd=True,
    )
    try:
        pipe.start()
        assert pipe.read(6) is None
        assert pipe._pipe is not None
        pipe._pipe.communicate(timeout=2)
        assert pipe.poll() == 0
    finally:
        pipe.close()


def test_spawn_failure_after_segment_start_rolls_back() -> None:
    """A decoder spawn error terminates an already started segment process."""
    before = _fd_count()
    segment = MagicMock()
    pipe = FFmpegPipe(
        "cam",
        LOGGER,
        logging.INFO,
        _decoder_command(),
        segment_command=["segment"],
        dedicated_rawvideo_fd=True,
    )
    with (
        patch(
            "viseron.components.ffmpeg.pipe.RestartablePopen",
            side_effect=[segment, OSError("spawn failed")],
        ),
        pytest.raises(OSError, match="spawn failed"),
    ):
        pipe.start()
    segment.terminate.assert_called_once()
    segment.communicate.assert_called_once()
    assert pipe._rawvideo_pipe is None
    assert pipe._stdout_log_pipe is None
    assert pipe._log_pipe is None
    assert _fd_count() == before


def test_pass_fds_contains_only_rawvideo_writer() -> None:
    """The decoder inherits the write end alone; the child retains the reader."""
    with patch("viseron.components.ffmpeg.pipe.RestartablePopen") as popen:
        pipe = FFmpegPipe(
            "cam", LOGGER, logging.INFO, _decoder_command(), dedicated_rawvideo_fd=True
        )
        pipe.start()
        call = popen.call_args
        (write_fd,) = call.kwargs["pass_fds"]
        assert call.args[0][-1] == f"pipe:{write_fd}"
        assert pipe._rawvideo_pipe is not None
        assert pipe._rawvideo_pipe.fileno() != write_fd
        with pytest.raises(OSError):
            os.fstat(write_fd)
        pipe.close()


def _forkserver_reader(result_queue: mp.Queue) -> None:
    """Run real FFmpegPipe in the forkserver child and report both cycles."""
    pipe = FFmpegPipe(
        "fork", LOGGER, logging.INFO, _decoder_command(), dedicated_rawvideo_fd=True
    )
    before = _fd_count()
    frames = []
    try:
        for _ in range(2):
            pipe.start()
            frames.append(pipe.read(6))
            frames.append(pipe.read(6))
            pipe.close()
        result_queue.put((frames, before, _fd_count()))
    finally:
        pipe.close()


def test_forkserver_child_owns_rawvideo_pipe() -> None:
    """Pickled command crosses forkserver; child creates FD and spawns decoder."""
    context = mp.get_context("forkserver")
    result_queue = context.Queue()
    process = context.Process(target=_forkserver_reader, args=(result_queue,))
    process.start()
    frames, before, after = result_queue.get(timeout=10)
    process.join(timeout=10)
    assert process.exitcode == 0
    assert frames == [b"abcdef", None, b"abcdef", None]
    assert after == before


def test_frame_reader_config_serializes_orin_selection() -> None:
    """The forkserver payload carries a bool and command, never a live FD."""
    config = FrameReaderConfig(
        "cam", _decoder_command(), None, 6, "info", [], (), logging.INFO, True
    )
    assert pickle.loads(pickle.dumps(config)) == config  # noqa: S301


def test_run_frame_reader_over_forkserver() -> None:
    """The production entrypoint queues only raw FD bytes from a real decoder."""
    context = mp.get_context("forkserver")
    frame_queue = context.Queue(maxsize=2)
    capture_frames = context.Event()
    decode_error = context.Event()
    capture_frames.set()
    config = FrameReaderConfig(
        "forkcam", _decoder_command(), None, 6, "info", [], (), logging.INFO, True
    )
    process = context.Process(
        target=run_frame_reader,
        args=(config, frame_queue, capture_frames, decode_error),
    )
    try:
        process.start()
        assert frame_queue.get(timeout=10) == b"abcdef"
    finally:
        capture_frames.clear()
        process.join(timeout=8)
        if process.is_alive():
            process.terminate()
            process.join(timeout=3)
        frame_queue.close()
    assert process.exitcode == -9  # run_frame_reader intentionally kills itself.
