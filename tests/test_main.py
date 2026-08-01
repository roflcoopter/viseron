"""Tests for viseron.__main__ signal handling."""

from __future__ import annotations

import logging
import signal
import threading
import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from viseron import __main__ as viseron_main

if TYPE_CHECKING:
    from collections.abc import Callable

    from _pytest.logging import LogCaptureFixture


def _make_viseron_mock() -> MagicMock:
    """Create a MagicMock standing in for a Viseron instance."""
    vis = MagicMock()
    vis.shutdown_event = threading.Event()
    vis.exit_code = 0
    return vis


class TestReloadConfigSafe:
    """Tests for the _reload_config_safe helper."""

    def test_calls_reload_config_with_vis(self) -> None:
        """_reload_config_safe should call reload_config with the given vis."""
        vis = _make_viseron_mock()
        with patch.object(viseron_main, "reload_config") as mock_reload_config:
            viseron_main._reload_config_safe(vis)
        mock_reload_config.assert_called_once_with(vis)

    def test_swallows_and_logs_exception(self, caplog: LogCaptureFixture) -> None:
        """Exceptions raised by reload_config must not propagate."""
        vis = _make_viseron_mock()
        with (
            patch.object(
                viseron_main,
                "reload_config",
                side_effect=RuntimeError("boom"),
            ),
            caplog.at_level(logging.ERROR, logger="viseron.main"),
        ):
            viseron_main._reload_config_safe(vis)  # must not raise

        assert "boom" in caplog.text


class TestMainSighupWiring:
    """Tests for SIGHUP wiring inside main()."""

    def test_sighup_triggers_reload_without_exiting_loop(self) -> None:
        """A SIGHUP should trigger a reload but keep the main loop running."""
        mock_vis = _make_viseron_mock()
        captured_handlers: dict[int, Callable[[], None]] = {}

        def fake_signal(signum: int, handler: Callable[[], None]) -> None:
            captured_handlers[signum] = handler

        reload_started = threading.Event()

        def fake_reload_config(_vis: object) -> None:
            reload_started.set()

        pause_calls = {"count": 0}

        def fake_pause() -> None:
            pause_calls["count"] += 1
            if pause_calls["count"] == 1:
                # Simulate a SIGHUP being delivered to the process.
                captured_handlers[signal.SIGHUP]()
                assert reload_started.wait(timeout=2), "reload was not triggered"
            else:
                # Simulate a real shutdown signal to end the loop.
                captured_handlers[signal.SIGTERM]()

        with (
            patch.object(viseron_main, "Viseron", return_value=mock_vis),
            patch.object(viseron_main, "enable_logging"),
            patch.object(viseron_main, "kill_zombie_processes"),
            patch.object(viseron_main, "setup_viseron"),
            patch.object(
                viseron_main, "reload_config", side_effect=fake_reload_config
            ) as mock_reload_config,
            patch.object(viseron_main, "NamedTimer"),
            patch("signal.signal", side_effect=fake_signal),
            patch("signal.pause", side_effect=fake_pause),
            patch("os.kill"),
        ):
            exit_code = viseron_main.main()

        assert signal.SIGHUP in captured_handlers
        mock_reload_config.assert_called_once_with(mock_vis)
        # Loop must have paused more than once: SIGHUP did not end it.
        assert pause_calls["count"] == 2
        assert exit_code == 0

    def test_second_sighup_ignored_while_reload_in_progress(
        self, caplog: LogCaptureFixture
    ) -> None:
        """Overlapping SIGHUP signals must not start a second reload thread."""
        mock_vis = _make_viseron_mock()
        captured_handlers: dict[int, Callable[[], None]] = {}

        def fake_signal(signum: int, handler: Callable[[], None]) -> None:
            captured_handlers[signum] = handler

        def fake_pause() -> None:
            # End the main loop immediately so we can drive the SIGHUP
            # handler manually afterwards.
            captured_handlers[signal.SIGTERM]()

        release_reload = threading.Event()
        reload_started = threading.Event()
        reload_call_count = {"n": 0}

        def slow_reload_config(_vis: object) -> None:
            reload_call_count["n"] += 1
            reload_started.set()
            release_reload.wait(timeout=2)

        # Keep all patches (especially reload_config) active for the entire
        # test: the SIGHUP handler closures are invoked manually below, after
        # main() has already returned, and must still hit the mocked
        # reload_config rather than the real implementation.
        with (
            patch.object(viseron_main, "Viseron", return_value=mock_vis),
            patch.object(viseron_main, "enable_logging"),
            patch.object(viseron_main, "kill_zombie_processes"),
            patch.object(viseron_main, "setup_viseron"),
            patch.object(viseron_main, "reload_config", side_effect=slow_reload_config),
            patch.object(viseron_main, "NamedTimer"),
            patch("signal.signal", side_effect=fake_signal),
            patch("signal.pause", side_effect=fake_pause),
            patch("os.kill"),
        ):
            viseron_main.main()

            assert signal.SIGHUP in captured_handlers
            sighup_handler = captured_handlers[signal.SIGHUP]

            try:
                with caplog.at_level(logging.WARNING, logger="viseron.main"):
                    sighup_handler()
                    assert reload_started.wait(timeout=2), "reload was not started"
                    sighup_handler()  # should be ignored, reload still in progress
                    time.sleep(0.05)  # give an errant second thread a chance to run
            finally:
                release_reload.set()

        assert reload_call_count["n"] == 1
        assert "already in progress" in caplog.text
