import { HttpResponse } from "msw";
import { getDayjs } from "tests/mocks/clock";

import * as types from "lib/types";

const TIMELAPSE_CAMERAS = ["camera1", "camera2"];
// A frame every 5 minutes for the last week
const TIMELAPSE_INTERVAL = 300;
const TIMELAPSE_DAYS = 7;

const timelapseFrame = (
  camera_identifier: string,
  timestamp: number,
): types.TimelapseFrame => ({
  file_key: timestamp,
  timestamp,
  path: `/file/${camera_identifier}/${timestamp.toString(16)}`,
});

// Periods without frames, as UNIX timestamps
export type TimelapseGap = { start: number; end: number };

const timelapseTimestamps = (
  start: number,
  end: number,
  gaps: TimelapseGap[] = [],
) => {
  const now = getDayjs().unix();
  const first = Math.max(start, now - TIMELAPSE_DAYS * 86400);
  const last = Math.min(end, now);
  const timestamps: number[] = [];
  for (
    let timestamp = Math.ceil(first / TIMELAPSE_INTERVAL) * TIMELAPSE_INTERVAL;
    timestamp <= last;
    timestamp += TIMELAPSE_INTERVAL
  ) {
    if (!gaps.some((gap) => timestamp >= gap.start && timestamp < gap.end)) {
      timestamps.push(timestamp);
    }
  }
  return timestamps;
};

const timelapseSummary = (
  camera_identifier: string,
): types.TimelapseCameraSummary => {
  const now = getDayjs().unix();
  const timestamps = timelapseTimestamps(0, now);
  const last = timestamps[timestamps.length - 1];
  return {
    camera_identifier,
    count: timestamps.length,
    first_timestamp: timestamps[0],
    last_timestamp: last,
    latest_frame: timelapseFrame(camera_identifier, last),
  };
};

export const timelapseSummaryResponse = () =>
  HttpResponse.json({
    cameras: Object.fromEntries(
      TIMELAPSE_CAMERAS.map((camera_identifier) => [
        camera_identifier,
        timelapseSummary(camera_identifier),
      ]),
    ),
  } as types.TimelapseSummaryResponse);

export const timelapseFramesResponse = (
  camera_identifier: string,
  start: number,
  end: number,
  maxFrames: number,
  gaps: TimelapseGap[],
) => {
  if (!TIMELAPSE_CAMERAS.includes(camera_identifier)) {
    return HttpResponse.json(
      { status: 404, error: "Not Found" },
      { status: 404 },
    );
  }
  const timestamps = timelapseTimestamps(start, end, gaps);
  // Downsample like the backend, keeping every nth frame
  const every = Math.ceil(timestamps.length / maxFrames);
  const frames = timestamps
    .filter((_timestamp, index) => index % every === 0)
    .map((timestamp) => timelapseFrame(camera_identifier, timestamp));
  return HttpResponse.json({
    camera_identifier,
    start,
    end,
    step: every > 1 ? every * TIMELAPSE_INTERVAL : null,
    total: timestamps.length,
    frames,
    stream:
      frames.length > 0
        ? { fps: 15, segment_frames: 60, width: 1280, height: 720 }
        : null,
  } as types.TimelapseFramesResponse);
};

export const timelapseDatesOfInterestResponse = () => {
  const now = getDayjs();
  const framesPerDay = 86400 / TIMELAPSE_INTERVAL;
  const framesToday = Math.floor(
    now.diff(now.startOf("day"), "second") / TIMELAPSE_INTERVAL,
  );
  return HttpResponse.json({
    dates_of_interest: Object.fromEntries(
      Array.from({ length: TIMELAPSE_DAYS + 1 }, (_, day) => [
        now.subtract(day, "day").format("YYYY-MM-DD"),
        { frames: day === 0 ? framesToday : framesPerDay },
      ]),
    ),
  } as types.TimelapseDatesOfInterest);
};
