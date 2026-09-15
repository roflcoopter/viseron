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
