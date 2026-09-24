"""Tests for fragmenter."""

from __future__ import annotations

import datetime
import os
import shutil
import tempfile
import threading
from unittest.mock import MagicMock, Mock, patch

import pytest
from apscheduler.jobstores.base import JobLookupError

from viseron.domains.camera.const import MP4BOX_PATH
from viseron.domains.camera.fragmenter import (
    Fragment,
    Fragmenter,
    FragmenterSubProcessWorker,
    _extract_extinf_number,
    _extract_program_date_time,
    generate_playlist,
    get_available_timespans,
    get_skipped_segment_count,
)
from viseron.helpers import utcnow

PLAYLIST_CONTENT = """#EXTM3U
#EXT-X-VERSION:7
#EXT-X-TARGETDURATION:6
#EXT-X-MEDIA-SEQUENCE:0
#EXT-X-PLAYLIST-TYPE:EVENT
#EXT-X-MAP:URI="init.mp4"
#EXTINF:6.001628,
#EXT-X-PROGRAM-DATE-TIME:2024-08-08T09:59:00.229+0000
1723111140.m4s
#EXTINF:4.010498,
#EXT-X-PROGRAM-DATE-TIME:2024-08-08T09:59:06.231+0000
1723111146.m4s
#EXTINF:5.957438,
#EXT-X-PROGRAM-DATE-TIME:2024-08-08T09:59:10.241+0000
1723111150.m4s
#EXTINF:5.021240,
#EXT-X-PROGRAM-DATE-TIME:2024-08-08T09:59:16.199+0000
1723111156.m4s
#EXTINF:4.983073,
#EXT-X-PROGRAM-DATE-TIME:2024-08-08T09:59:21.220+0000
1723111161.m4s
#EXTINF:4.986003,
#EXT-X-PROGRAM-DATE-TIME:2024-08-08T09:59:26.203+0000
1723111166.m4s
#EXTINF:4.987305,
#EXT-X-PROGRAM-DATE-TIME:2024-08-08T09:59:31.189+0000
1723111171.m4s"""


def test_generate_playlist() -> None:
    """Test generate_playlist."""
    now = utcnow()
    fragments = [
        Fragment("test1.mp4", "/test/test1.mp4", 5.1, now),
        Fragment("test2.mp4", "/test/test2.mp4", 4.123, now),
    ]
    program_date_time = now.isoformat(timespec="milliseconds")

    playlist = generate_playlist(fragments, "/test/init.mp4", end=True)
    assert (
        playlist
        == f"""#EXTM3U
#EXT-X-VERSION:6
#EXT-X-MEDIA-SEQUENCE:0
#EXT-X-TARGETDURATION:6
#EXT-X-INDEPENDENT-SEGMENTS
#EXT-X-MAP:URI="/test/init.mp4"
#EXT-X-PROGRAM-DATE-TIME:{program_date_time}
#EXTINF:5.1,
/test/test1.mp4
#EXT-X-PROGRAM-DATE-TIME:{program_date_time}
#EXTINF:4.123,
/test/test2.mp4
#EXT-X-ENDLIST"""
    )


PLAYLIST_BASE_TIME = datetime.datetime(2024, 1, 1)


def _playlist_segment(index: int, program_date_time: str) -> list[str]:
    return [
        f"#EXT-X-PROGRAM-DATE-TIME:2024-01-01T{program_date_time}+00:00",
        "#EXTINF:5.0,",
        f"/test/{index}.m4s",
    ]


@pytest.mark.parametrize(
    ("offsets", "can_skip_until", "max_skipped_segments", "end", "expected"),
    [
        pytest.param(
            [0, 5, 10],
            10,
            0,
            False,
            [
                "#EXTM3U",
                "#EXT-X-VERSION:6",
                "#EXT-X-MEDIA-SEQUENCE:0",
                "#EXT-X-TARGETDURATION:5",
                "#EXT-X-SERVER-CONTROL:CAN-SKIP-UNTIL=10",
                "#EXT-X-INDEPENDENT-SEGMENTS",
                '#EXT-X-MAP:URI="/test/init.mp4"',
                *_playlist_segment(1, "00:00:00.000"),
                *_playlist_segment(2, "00:00:05.000"),
                *_playlist_segment(3, "00:00:10.000"),
            ],
            id="server_control_without_skip",
        ),
        pytest.param(
            [0, 5, 10],
            10,
            3,
            False,
            [
                "#EXTM3U",
                "#EXT-X-VERSION:9",
                "#EXT-X-MEDIA-SEQUENCE:0",
                "#EXT-X-TARGETDURATION:5",
                "#EXT-X-SERVER-CONTROL:CAN-SKIP-UNTIL=10",
                "#EXT-X-INDEPENDENT-SEGMENTS",
                "#EXT-X-SKIP:SKIPPED-SEGMENTS=1",
                '#EXT-X-MAP:URI="/test/init.mp4"',
                *_playlist_segment(2, "00:00:05.000"),
                *_playlist_segment(3, "00:00:10.000"),
            ],
            id="delta_update",
        ),
        pytest.param(
            [0, 20, 25],
            10,
            3,
            False,
            [
                "#EXTM3U",
                "#EXT-X-VERSION:9",
                "#EXT-X-MEDIA-SEQUENCE:0",
                "#EXT-X-TARGETDURATION:5",
                "#EXT-X-SERVER-CONTROL:CAN-SKIP-UNTIL=10",
                "#EXT-X-INDEPENDENT-SEGMENTS",
                "#EXT-X-SKIP:SKIPPED-SEGMENTS=1",
                '#EXT-X-MAP:URI="/test/init.mp4"',
                "#EXT-X-DISCONTINUITY",
                *_playlist_segment(2, "00:00:20.000"),
                *_playlist_segment(3, "00:00:25.000"),
            ],
            id="delta_update_keeps_discontinuity_after_skipped_segment",
        ),
        pytest.param(
            [0, 20, 25, 30],
            10,
            3,
            False,
            [
                "#EXTM3U",
                "#EXT-X-VERSION:9",
                "#EXT-X-MEDIA-SEQUENCE:0",
                "#EXT-X-TARGETDURATION:5",
                "#EXT-X-SERVER-CONTROL:CAN-SKIP-UNTIL=10",
                "#EXT-X-INDEPENDENT-SEGMENTS",
                "#EXT-X-SKIP:SKIPPED-SEGMENTS=2",
                '#EXT-X-MAP:URI="/test/init.mp4"',
                *_playlist_segment(3, "00:00:25.000"),
                *_playlist_segment(4, "00:00:30.000"),
            ],
            # Skipped segments remain part of the playlist, so the discontinuity
            # sequence is not advanced and the client restores the skipped
            # discontinuity from its previous playlist
            id="delta_update_skips_discontinuity_in_skipped_segments",
        ),
        pytest.param(
            [0, 5, 10, 15],
            5,
            1,
            False,
            [
                "#EXTM3U",
                "#EXT-X-VERSION:9",
                "#EXT-X-MEDIA-SEQUENCE:0",
                "#EXT-X-TARGETDURATION:5",
                "#EXT-X-SERVER-CONTROL:CAN-SKIP-UNTIL=5",
                "#EXT-X-INDEPENDENT-SEGMENTS",
                "#EXT-X-SKIP:SKIPPED-SEGMENTS=1",
                '#EXT-X-MAP:URI="/test/init.mp4"',
                *_playlist_segment(2, "00:00:05.000"),
                *_playlist_segment(3, "00:00:10.000"),
                *_playlist_segment(4, "00:00:15.000"),
            ],
            id="delta_update_limited_by_max_skipped_segments",
        ),
        pytest.param(
            [0, 5, 10],
            30,
            3,
            False,
            [
                "#EXTM3U",
                "#EXT-X-VERSION:6",
                "#EXT-X-MEDIA-SEQUENCE:0",
                "#EXT-X-TARGETDURATION:5",
                "#EXT-X-SERVER-CONTROL:CAN-SKIP-UNTIL=30",
                "#EXT-X-INDEPENDENT-SEGMENTS",
                '#EXT-X-MAP:URI="/test/init.mp4"',
                *_playlist_segment(1, "00:00:00.000"),
                *_playlist_segment(2, "00:00:05.000"),
                *_playlist_segment(3, "00:00:10.000"),
            ],
            id="playlist_shorter_than_skip_boundary",
        ),
        pytest.param(
            [0, 5, 10],
            10,
            3,
            True,
            [
                "#EXTM3U",
                "#EXT-X-VERSION:6",
                "#EXT-X-MEDIA-SEQUENCE:0",
                "#EXT-X-TARGETDURATION:5",
                "#EXT-X-INDEPENDENT-SEGMENTS",
                '#EXT-X-MAP:URI="/test/init.mp4"',
                *_playlist_segment(1, "00:00:00.000"),
                *_playlist_segment(2, "00:00:05.000"),
                *_playlist_segment(3, "00:00:10.000"),
                "#EXT-X-ENDLIST",
            ],
            id="ended_playlist_ignores_delta_updates",
        ),
    ],
)
def test_generate_playlist_delta_update(
    offsets: list[int],
    can_skip_until: float,
    max_skipped_segments: int,
    end: bool,
    expected: list[str],
) -> None:
    """Test generate_playlist with Playlist Delta Updates."""
    fragments = [
        Fragment(
            f"{index}.m4s",
            f"/test/{index}.m4s",
            5.0,
            PLAYLIST_BASE_TIME + datetime.timedelta(seconds=offset),
        )
        for index, offset in enumerate(offsets, start=1)
    ]

    playlist = generate_playlist(
        fragments,
        "/test/init.mp4",
        end=end,
        can_skip_until=can_skip_until,
        max_skipped_segments=max_skipped_segments,
    )

    assert playlist == "\n".join(expected)


@pytest.mark.parametrize(
    ("durations", "skip_boundary", "expected"),
    [
        pytest.param([5.0] * 15, 30, 9, id="skips_segments_outside_boundary"),
        pytest.param([5.0] * 6, 30, 0, id="playlist_equal_to_boundary"),
        pytest.param([5.0] * 3, 30, 0, id="playlist_shorter_than_boundary"),
        pytest.param([], 30, 0, id="empty_playlist"),
        pytest.param(
            [10.0, 10.0, 4.0, 6.0, 5.0, 5.0, 5.0, 5.0], 30, 2, id="uneven_durations"
        ),
    ],
)
def test_get_skipped_segment_count(
    durations: list[float], skip_boundary: float, expected: int
) -> None:
    """Test that the fragments at the end of the playlist cover the skip boundary."""
    fragments = [
        Fragment(f"{index}.m4s", f"/test/{index}.m4s", duration, PLAYLIST_BASE_TIME)
        for index, duration in enumerate(durations)
    ]

    assert get_skipped_segment_count(fragments, skip_boundary) == expected


@pytest.mark.parametrize(
    ("segment_starts", "expected"),
    [
        pytest.param([], [], id="no_segments"),
        pytest.param(
            [0, 5, 10],
            [{"start": 0, "end": 15, "duration": 15}],
            id="contiguous",
        ),
        pytest.param(
            [0, 5, 15],
            [{"start": 0, "end": 20, "duration": 20}],
            id="gap_within_one_segment_duration",
        ),
        pytest.param(
            [0, 5, 10, 1000, 1005],
            [
                {"start": 0, "end": 15, "duration": 15},
                {"start": 1000, "end": 1010, "duration": 10},
            ],
            id="gap",
        ),
        pytest.param(
            [0, 5, 1000],
            [
                {"start": 0, "end": 10, "duration": 10},
                {"start": 1000, "end": 1005, "duration": 5},
            ],
            id="single_segment_after_gap",
        ),
    ],
)
def test_get_available_timespans(
    segment_starts: list[int], expected: list[dict[str, int]]
) -> None:
    """Test that segments are merged into timespans that split on gaps."""
    segments = [
        MagicMock(
            orig_ctime=datetime.datetime.fromtimestamp(start, tz=datetime.timezone.utc),
            duration=5,
        )
        for start in segment_starts
    ]
    with patch(
        "viseron.domains.camera.fragmenter.get_time_period_fragments",
        return_value=segments,
    ):
        assert get_available_timespans(MagicMock(), ["test"], 0) == expected


class TestFragmenter:
    """Tests for Fragmenter."""

    def setup_method(self):
        """Set up test method."""
        self.vis = MagicMock()
        self.camera = MagicMock()
        self.camera.identifier = "test_camera"
        self.camera.temp_segments_folder = tempfile.mkdtemp()
        self.camera.segments_folder = tempfile.mkdtemp()
        self.fragmenter = Fragmenter(self.vis, self.camera)
        self.fragmenter.start()

    def teardown_method(self):
        """Tear down test method."""
        self.fragmenter.unload()
        shutil.rmtree(self.camera.temp_segments_folder)
        shutil.rmtree(self.camera.segments_folder)

    @patch("viseron.domains.camera.fragmenter.sp.run")
    def test_mp4box_command(self, mock_sp_run: Mock):
        """Test mp4box command generation."""
        mock_sp_run.return_value = MagicMock()
        self.fragmenter._fragment_worker._mp4box_command("test.mp4")
        mock_sp_run.assert_called_once_with(
            [
                MP4BOX_PATH,
                "-logs",
                "dash@error:ncl",
                "-noprog",
                "-dash",
                "10000",
                "-rap",
                "-frag-rap",
                "-segment-name",
                "clip_",
                "-out",
                os.path.join(self.camera.temp_segments_folder, "test", "master.m3u8"),
                os.path.join(self.camera.temp_segments_folder, "test.mp4"),
            ],
            stdout=self.fragmenter._fragment_worker._log_pipe,
            stderr=self.fragmenter._fragment_worker._log_pipe,
            check=True,
        )

    @patch("viseron.domains.camera.fragmenter.shutil.move")
    def test_move_to_segments_folder_mp4box(self, mock_shutil_move: Mock):
        """Test that the files are moved to the segments folder."""
        mock_shutil_move.return_value = MagicMock()
        self.fragmenter._fragment_worker._move_to_segments_folder_mp4box("test.mp4")
        mock_shutil_move.assert_any_call(
            os.path.join(self.camera.temp_segments_folder, "test", "clip_1.m4s"),
            os.path.join(self.camera.segments_folder, "test.m4s"),
        )

        mock_shutil_move.assert_any_call(
            os.path.join(self.camera.temp_segments_folder, "test", "clip_init.mp4"),
            os.path.join(self.camera.segments_folder, "init.mp4"),
        )
        assert mock_shutil_move.call_count == 2

    def test_drain_waits_for_child_process(self) -> None:
        """Drain returns once the child process has replied."""
        assert self.fragmenter._fragment_worker.drain(timeout=10)


@pytest.mark.parametrize(
    ("cmd", "expected_handled", "expected_result"),
    [
        pytest.param("fragment", 5, None, id="fragment_limits_batch"),
        pytest.param("drain", 7, {"drained": True}, id="drain_handles_all"),
        pytest.param("unknown", 0, None, id="unknown_cmd"),
    ],
)
def test_worker_work_input(
    cmd: str, expected_handled: int, expected_result: dict | None
) -> None:
    """Drain fragments every pending segment and replies when done."""
    worker = MagicMock()
    files = [f"{i}.m4s" for i in range(7)]

    with patch(
        "viseron.domains.camera.fragmenter._get_mp4_files_to_fragment",
        return_value=files,
    ):
        result = FragmenterSubProcessWorker.work_input(worker, {"cmd": cmd})

    assert result == expected_result
    assert worker._handle_m4s.call_count == expected_handled


def test_worker_does_not_stop_on_shutdown_signal() -> None:
    """Only the Fragmenter stops the worker, so it is never stopped concurrently."""
    vis = MagicMock()

    with (
        patch("viseron.helpers.child_process_worker.RestartableThread"),
        patch("viseron.helpers.child_process_worker.RestartableProcess"),
    ):
        worker = FragmenterSubProcessWorker(
            vis, MagicMock(), MagicMock(), "/tmp/temp", "/tmp/segments", MagicMock()
        )
    worker._log_pipe.close()

    vis.register_signal_handler.assert_not_called()


class TestFragmenterLifecycle:
    """Tests for starting and stopping the Fragmenter child process."""

    def setup_method(self) -> None:
        """Set up test method."""
        self.vis = MagicMock()
        self.camera = MagicMock()
        self.camera.identifier = "test_camera"
        self.camera.temp_segments_folder = tempfile.mkdtemp()
        self.camera.temp_timelapse_folder = None
        self.camera.stopped = threading.Event()
        self._worker_patcher = patch(
            "viseron.domains.camera.fragmenter.FragmenterSubProcessWorker"
        )
        self.mock_worker_cls = self._worker_patcher.start()
        self.mock_worker = self.mock_worker_cls.return_value
        self.mock_job = self.vis.background_scheduler.add_job.return_value
        self.fragmenter = Fragmenter(self.vis, self.camera)

    def teardown_method(self) -> None:
        """Tear down test method."""
        self._worker_patcher.stop()
        shutil.rmtree(self.camera.temp_segments_folder)

    def test_init_does_not_start_worker(self) -> None:
        """No child process is spawned until the camera is started."""
        self.mock_worker_cls.assert_not_called()
        self.vis.background_scheduler.add_job.assert_not_called()

    def test_start_is_idempotent(self) -> None:
        """Starting twice spawns a single worker and job."""
        self.fragmenter.start()
        self.fragmenter.start()

        self.mock_worker_cls.assert_called_once()
        self.vis.background_scheduler.add_job.assert_called_once()

    def test_stop_is_idempotent(self) -> None:
        """Stopping twice stops the worker and removes the job only once."""
        self.fragmenter.start()
        self.fragmenter.stop()
        self.fragmenter.stop()

        self.mock_worker.stop.assert_called_once_with()
        self.mock_job.remove.assert_called_once_with()

    @pytest.mark.parametrize(
        "drained",
        [
            pytest.param(True, id="drained"),
            pytest.param(False, id="drain_timed_out"),
        ],
    )
    def test_stop_drains_before_stopping_worker(self, drained: bool) -> None:
        """Pending segments are fragmented before the worker is stopped."""
        manager = MagicMock()
        manager.attach_mock(self.mock_job.remove, "remove_job")
        manager.attach_mock(self.mock_worker.drain, "drain")
        manager.attach_mock(self.mock_worker.stop, "stop")
        self.mock_worker.drain.return_value = drained
        self.fragmenter.start()

        self.fragmenter.stop()

        assert [name for name, _, _ in manager.mock_calls] == [
            "remove_job",
            "drain",
            "stop",
        ]

    def test_stop_after_scheduler_removed_job(self) -> None:
        """Viseron removes all jobs before shutdown, which must not skip the stop."""
        self.mock_job.remove.side_effect = JobLookupError("fragment_test_camera")
        self.fragmenter.start()

        self.fragmenter.stop()

        self.mock_worker.stop.assert_called_once_with()

    def test_shutdown_stops_worker(self) -> None:
        """The shutdown signal stops a worker whose camera was not stopped by NVR."""
        self.camera.stopped.set()
        self.fragmenter.start()

        self.fragmenter._shutdown()

        self.mock_worker.drain.assert_called_once()
        self.mock_worker.stop.assert_called_once_with()

    def test_shutdown_during_camera_stop_stops_worker_once(self) -> None:
        """The shutdown signal waits for a stop_camera() drain instead of racing it."""
        drain_started = threading.Event()
        release_drain = threading.Event()

        def blocking_drain(**_kwargs: float) -> bool:
            drain_started.set()
            return release_drain.wait(5)

        self.mock_worker.drain.side_effect = blocking_drain
        self.fragmenter.start()
        self.camera.stopped.set()
        camera_stop = threading.Thread(target=self.fragmenter.stop)
        shutdown = threading.Thread(target=self.fragmenter._shutdown)

        camera_stop.start()
        assert drain_started.wait(5)
        shutdown.start()
        shutdown.join(0.2)
        # Blocked on the lock held by the draining camera stop
        assert shutdown.is_alive()
        release_drain.set()
        camera_stop.join(5)
        shutdown.join(5)

        self.mock_worker.drain.assert_called_once()
        self.mock_worker.stop.assert_called_once_with()

    def test_stop_without_start(self) -> None:
        """Stopping a fragmenter that was never started does nothing."""
        self.fragmenter.stop()

        self.mock_worker.stop.assert_not_called()

    def test_restart_spawns_new_worker(self) -> None:
        """A stopped worker cannot be reused, so a new one is spawned on start."""
        self.fragmenter.start()
        self.fragmenter.stop()
        self.fragmenter.start()

        assert self.mock_worker_cls.call_count == 2
        assert self.vis.background_scheduler.add_job.call_count == 2

    def test_unload_stops_worker(self) -> None:
        """Unloading a started fragmenter stops the worker."""
        self.fragmenter.start()
        self.fragmenter.unload()

        self.mock_worker.stop.assert_called_once_with()
        self.mock_job.remove.assert_called_once_with()

    def test_fragment_command_after_stop(self) -> None:
        """A job run racing with stop does not send work to the stopped worker."""
        self.fragmenter.start()
        self.fragmenter.stop()

        self.fragmenter._fragment_command()

        self.mock_worker.input_queue.put.assert_not_called()

    def test_fragment_command_while_started(self) -> None:
        """A running fragmenter sends fragment commands to its worker."""
        self.fragmenter.start()

        self.fragmenter._fragment_command()

        self.mock_worker.input_queue.put.assert_called_once_with(
            {"cmd": "fragment"}, timeout=1
        )


def test_extract_extinf_number():
    """Test _extract_extinf_number."""
    extinf_number = _extract_extinf_number(PLAYLIST_CONTENT, "1723111150.m4s")
    assert extinf_number == 5.957438


def test_extract_program_date_time() -> None:
    """Test _extract_program_date_time."""
    date_time_tag = _extract_program_date_time(PLAYLIST_CONTENT, "1723111156.m4s")
    assert date_time_tag == datetime.datetime(
        2024, 8, 8, 9, 59, 16, 199000, tzinfo=datetime.timezone.utc
    )
