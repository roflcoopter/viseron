"""Test the query functions."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import insert

from tests.common import BaseTestWithRecordings
from viseron.components.storage.const import (
    TIER_CATEGORY_TIMELAPSE,
    TIER_SUBCATEGORY_TIMELAPSE,
)
from viseron.components.storage.models import Files
from viseron.components.storage.queries import (
    TimelapseFrame,
    TimelapseFrames,
    TimelapseSummary,
    get_recording_fragments,
    get_timelapse_frame_paths,
    get_time_period_fragments,
    get_timelapse_days,
    get_timelapse_frames,
    get_timelapse_summary,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session


class TestQueries(BaseTestWithRecordings):
    """Test the moving of files query functions."""

    def test_get_recording_fragments(self):
        """Test get_recording_fragments."""
        # Simulate a file that has been moved a up tier but have not been removed
        # from the previous tier yet
        with self._get_db_session() as session:
            created_at = self._now + datetime.timedelta(seconds=55)
            timestamp = self._now + datetime.timedelta(seconds=25)
            filename = f"{int(timestamp.timestamp())}.m4s"
            session.execute(
                insert(Files).values(
                    tier_id=1,
                    tier_path="/tier2/",
                    camera_identifier="test",
                    category="recorder",
                    subcategory="segments",
                    path=f"/tier2/{filename}",
                    directory="tier2",
                    filename=filename,
                    size=10,
                    orig_ctime=timestamp,
                    duration=5,
                    created_at=created_at,
                )
            )
            session.commit()

        files = get_recording_fragments(3, 5, self._get_db_session)
        assert len(files) == 4
        assert files[0].id == 9
        assert files[1].id == 31
        assert files[1].tier_id == 1
        assert files[2].id == 13
        assert files[3].id == 15

    def test_get_time_period_fragments(self):
        """Test get_recording_fragments."""
        with self._get_db_session() as session:
            # Simulate a file that has been moved a up tier but have not been removed
            # from the previous tier yet
            created_at = self._now + datetime.timedelta(seconds=55)
            timestamp = self._now + datetime.timedelta(seconds=25)
            filename = f"{int(timestamp.timestamp())}.m4s"
            session.execute(
                insert(Files).values(
                    tier_id=1,
                    tier_path="/tier2/",
                    camera_identifier="test",
                    category="recorder",
                    subcategory="segments",
                    path=f"/tier2/{filename}",
                    directory="tier2",
                    filename=filename,
                    size=10,
                    orig_ctime=timestamp,
                    duration=5,
                    created_at=created_at,
                )
            )

            # Simulate a file that has broken metadata
            created_at = self._now + datetime.timedelta(seconds=500)
            timestamp = self._now + datetime.timedelta(seconds=500)
            filename = f"{int(timestamp.timestamp())}.m4s"
            session.execute(
                insert(Files).values(
                    tier_id=0,
                    tier_path="/tier1/",
                    camera_identifier="test",
                    category="recorder",
                    subcategory="segments",
                    path=f"/tier1/{filename}",
                    directory="tier1",
                    filename=filename,
                    size=10,
                    orig_ctime=timestamp,
                    duration=None,
                    created_at=created_at,
                )
            )
            session.commit()

        files = get_time_period_fragments(
            ["test"],
            0,
            None,
            self._get_db_session,
            self._now + datetime.timedelta(days=365),
        )
        assert len(files) == 15
        assert files[4].tier_id == 0
        assert files[5].tier_id == 1


_TIMELAPSE_EPOCH = 1_700_000_000


def _insert_timelapse_frame(
    session: Session,
    offset: float,
    file_key: int,
    tier_id: int = 0,
    camera_identifier: str = "test",
    category: str = TIER_CATEGORY_TIMELAPSE,
) -> None:
    timestamp = datetime.datetime.fromtimestamp(
        _TIMELAPSE_EPOCH + offset, tz=datetime.timezone.utc
    )
    filename = f"{int(timestamp.timestamp())}.jpg"
    session.execute(
        insert(Files).values(
            file_key=file_key,
            tier_id=tier_id,
            tier_path=f"/tier{tier_id}/",
            camera_identifier=camera_identifier,
            category=category,
            subcategory=TIER_SUBCATEGORY_TIMELAPSE,
            path=f"/tier{tier_id}/timelapse/{camera_identifier}/{filename}",
            directory=f"/tier{tier_id}/timelapse/{camera_identifier}",
            filename=filename,
            size=10,
            orig_ctime=timestamp,
            duration=None,
        )
    )


def _frame_offsets(frames: TimelapseFrames) -> list[float]:
    return [frame.orig_ctime.timestamp() - _TIMELAPSE_EPOCH for frame in frames.frames]


def test_get_timelapse_frames_returns_all_frames_in_range(
    get_db_session: Callable[[], Session],
) -> None:
    """Frames in range are returned in order, one per file_key, lowest tier first."""
    with get_db_session() as session:
        for i in range(5):
            _insert_timelapse_frame(session, i * 5, file_key=i + 1)
        # Tier copy of file_key 3 that has not been removed from tier 0 yet
        _insert_timelapse_frame(session, 10, file_key=3, tier_id=1)
        _insert_timelapse_frame(session, 30, file_key=6)
        _insert_timelapse_frame(session, 5, file_key=7, camera_identifier="other")
        _insert_timelapse_frame(session, 7, file_key=8, category="snapshots")
        session.commit()

    frames = get_timelapse_frames(
        "test", _TIMELAPSE_EPOCH + 5, _TIMELAPSE_EPOCH + 20, 100, get_db_session
    )

    assert frames.total == 4
    assert frames.step is None
    assert _frame_offsets(frames) == [5, 10, 15, 20]
    assert [frame.file_key for frame in frames.frames] == [2, 3, 4, 5]
    assert frames.frames[1].path == "/tier0/timelapse/test/1700000010.jpg"


def test_get_timelapse_frames_downsamples(
    get_db_session: Callable[[], Session],
) -> None:
    """Frames are bucketed by time so at most max_frames are returned."""
    with get_db_session() as session:
        for i in range(100):
            _insert_timelapse_frame(session, i * 5, file_key=i + 1)
            _insert_timelapse_frame(session, i * 5, file_key=i + 1, tier_id=1)
        session.commit()

    frames = get_timelapse_frames(
        "test", _TIMELAPSE_EPOCH, _TIMELAPSE_EPOCH + 10_000, 10, get_db_session
    )

    assert frames.total == 100
    assert frames.step == pytest.approx(49.5)
    assert _frame_offsets(frames) == [i * 50 for i in range(10)]
    assert {frame.path.split("/")[1] for frame in frames.frames} == {"tier0"}


def test_get_timelapse_frames_empty(
    get_db_session: Callable[[], Session],
) -> None:
    """An empty range returns no frames."""
    frames = get_timelapse_frames(
        "test", _TIMELAPSE_EPOCH, _TIMELAPSE_EPOCH + 100, 10, get_db_session
    )

    assert frames == TimelapseFrames(total=0, step=None, frames=[])


def test_get_timelapse_summary(
    get_db_session: Callable[[], Session],
) -> None:
    """Summary counts unique frames and returns the latest from the lowest tier."""
    with get_db_session() as session:
        _insert_timelapse_frame(session, 0, file_key=1)
        _insert_timelapse_frame(session, 0, file_key=1, tier_id=1)
        _insert_timelapse_frame(session, 60, file_key=2, tier_id=1)
        _insert_timelapse_frame(session, 60, file_key=2)
        _insert_timelapse_frame(session, 30, file_key=3, camera_identifier="other")
        _insert_timelapse_frame(session, 90, file_key=4, category="snapshots")
        session.commit()

    summary = get_timelapse_summary(["test", "other", "empty"], get_db_session)

    first = datetime.datetime.fromtimestamp(_TIMELAPSE_EPOCH, tz=datetime.timezone.utc)
    last = first + datetime.timedelta(seconds=60)
    assert summary["test"] == TimelapseSummary(
        count=2,
        first=first,
        last=last,
        latest_frame=TimelapseFrame(
            file_key=2,
            path="/tier0/timelapse/test/1700000060.jpg",
            orig_ctime=last,
        ),
    )
    assert summary["other"].count == 1
    assert summary["empty"] == TimelapseSummary(
        count=0, first=None, last=None, latest_frame=None
    )


@pytest.mark.parametrize(
    ("utc_offset", "expected"),
    [
        pytest.param(
            datetime.timedelta(0),
            {"2023-11-14": 2, "2023-11-15": 1},
            id="utc",
        ),
        pytest.param(
            datetime.timedelta(hours=-23),
            {"2023-11-13": 1, "2023-11-14": 2},
            id="negative_offset",
        ),
        pytest.param(
            datetime.timedelta(hours=1),
            {"2023-11-14": 1, "2023-11-15": 2},
            id="positive_offset",
        ),
    ],
)
def test_get_timelapse_days(
    get_db_session: Callable[[], Session],
    utc_offset: datetime.timedelta,
    expected: dict[str, int],
) -> None:
    """Unique frames are counted per local day."""
    # _TIMELAPSE_EPOCH is 2023-11-14 22:13:20 UTC
    with get_db_session() as session:
        _insert_timelapse_frame(session, 0, file_key=1)
        _insert_timelapse_frame(session, 0, file_key=1, tier_id=1)
        _insert_timelapse_frame(session, 3600, file_key=2)
        _insert_timelapse_frame(session, 7200, file_key=3)
        _insert_timelapse_frame(session, 7200, file_key=4, camera_identifier="other")
        session.commit()

    assert get_timelapse_days("test", utc_offset, get_db_session) == expected


def test_get_timelapse_frame_paths(
    get_db_session: Callable[[], Session],
) -> None:
    """Every tier copy of the requested timelapse frames is returned."""
    with get_db_session() as session:
        _insert_timelapse_frame(session, 0, file_key=1, tier_id=1)
        _insert_timelapse_frame(session, 0, file_key=1)
        _insert_timelapse_frame(session, 5, file_key=2)
        _insert_timelapse_frame(session, 10, file_key=3)
        _insert_timelapse_frame(session, 0, file_key=4, camera_identifier="other")
        _insert_timelapse_frame(session, 15, file_key=5, category="snapshots")
        session.commit()

    assert get_timelapse_frame_paths("test", [1, 2, 4, 5, 6], get_db_session) == {
        1: [
            "/tier0/timelapse/test/1700000000.jpg",
            "/tier1/timelapse/test/1700000000.jpg",
        ],
        2: ["/tier0/timelapse/test/1700000005.jpg"],
    }
