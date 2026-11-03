import { HttpResponse } from "msw";
import { getDayjs, getDayjsFromDateString } from "tests/mocks/clock";

import * as types from "lib/types";

const EVENT_CAMERAS = ["camera1", "camera2", "camera3"];
// An event every 30 minutes per camera for the last week
const EVENT_INTERVAL = 1800;
const EVENT_OFFSET = 300;
const EVENT_CAMERA_OFFSET = 600;
const EVENT_DAYS = 7;
const MOTION_DURATION = 40;
const RECORDING_DURATION = 60;
const LOOKBACK = 5;

const isoString = (timestamp: number) =>
  new Date(timestamp * 1000).toISOString();

const timedEvent = (
  camera_identifier: string,
  id: number,
  start: number,
  end: number,
) => ({
  camera_identifier,
  id,
  created_at: isoString(start),
  created_at_timestamp: start,
  lookback: LOOKBACK,
  start_time: isoString(start),
  start_timestamp: start,
  end_time: isoString(end),
  end_timestamp: end,
  duration: end - start,
});

const snapshotEvent = (
  camera_identifier: string,
  id: number,
  timestamp: number,
  type: types.CameraSnapshotEvent["type"],
) => ({
  camera_identifier,
  id,
  created_at: isoString(timestamp),
  created_at_timestamp: timestamp,
  lookback: LOOKBACK,
  time: isoString(timestamp),
  timestamp,
  snapshot_path: `/files/tier1/snapshots/${camera_identifier}/${type}-${id}.jpg`,
});

// Each event is motion followed by a recording, and depending on the slot
// an object with the post processor result that would follow it
const generateEvents = (
  camera_identifier: string,
  slot: number,
  start: number,
): types.CameraEvent[] => {
  const cameraIndex = EVENT_CAMERAS.indexOf(camera_identifier);
  const id = slot * EVENT_CAMERAS.length + cameraIndex;
  // Shifted per camera so consecutive events across cameras differ
  const kind = (slot + cameraIndex) % 4;
  const events: types.CameraEvent[] = [
    {
      ...timedEvent(camera_identifier, id, start, start + MOTION_DURATION),
      type: "motion",
      snapshot_path: `/files/tier1/snapshots/${camera_identifier}/motion-${id}.jpg`,
    },
    {
      ...timedEvent(
        camera_identifier,
        id,
        start - LOOKBACK,
        start + RECORDING_DURATION,
      ),
      type: "recording",
      trigger_type: kind === 3 ? "motion" : "object",
      hls_url: `/api/v1/hls/${camera_identifier}/${id}/index.m3u8`,
      thumbnail_path: `/files/tier1/thumbnails/${camera_identifier}/${id}.jpg`,
    },
  ];
  const detected = start + 5;
  const processed = start + 10;
  switch (kind) {
    case 0:
      events.push(
        {
          ...snapshotEvent(camera_identifier, id, detected, "object"),
          type: "object",
          label: "person",
          confidence: 0.91,
        },
        {
          ...snapshotEvent(
            camera_identifier,
            id,
            processed,
            "face_recognition",
          ),
          type: "face_recognition",
          data: { name: slot % 8 === 0 ? "jane" : "unknown", confidence: 0.84 },
        },
      );
      break;
    case 1:
      events.push(
        {
          ...snapshotEvent(camera_identifier, id, detected, "object"),
          type: "object",
          label: "car",
          confidence: 0.88,
        },
        {
          ...snapshotEvent(
            camera_identifier,
            id,
            processed,
            "license_plate_recognition",
          ),
          type: "license_plate_recognition",
          data: {
            camera_identifier,
            known: slot % 8 === 1,
            plate: slot % 8 === 1 ? "ABC123" : "XYZ789",
            confidence: 0.93,
          },
        },
      );
      break;
    case 2:
      events.push(
        {
          ...snapshotEvent(camera_identifier, id, detected, "object"),
          type: "object",
          label: "dog",
          confidence: 0.76,
        },
        {
          ...snapshotEvent(
            camera_identifier,
            id,
            processed,
            "image_classification",
          ),
          type: "image_classification",
          data: {
            camera_identifier,
            label: "golden retriever",
            confidence: 0.81,
          },
        },
      );
      break;
    default:
      break;
  }
  return events;
};

// Events of incidents that started within the range and have finished by now
export const cameraEvents = (
  camera_identifier: string,
  from: number,
  to: number,
): types.CameraEvent[] => {
  if (!EVENT_CAMERAS.includes(camera_identifier)) {
    return [];
  }
  const now = getDayjs().unix();
  const offset =
    EVENT_OFFSET +
    EVENT_CAMERAS.indexOf(camera_identifier) * EVENT_CAMERA_OFFSET;
  const first = Math.max(from, now - EVENT_DAYS * 86400);
  const last = Math.min(to, now - RECORDING_DURATION);
  const events: types.CameraEvent[] = [];
  for (
    let slot = Math.ceil((first - offset) / EVENT_INTERVAL);
    slot * EVENT_INTERVAL + offset <= last;
    slot++
  ) {
    events.push(
      ...generateEvents(
        camera_identifier,
        slot,
        slot * EVENT_INTERVAL + offset,
      ),
    );
  }
  return events;
};

const dayRange = (date: string) => {
  const day = getDayjsFromDateString(date);
  return { from: day.unix(), to: day.add(1, "day").unix() - 1 };
};

export const cameraEventsResponse = (
  camera_identifier: string,
  searchParams: URLSearchParams,
) => {
  const date = searchParams.get("date");
  const { from, to } = date
    ? dayRange(date)
    : {
        from: Number(searchParams.get("time_from")),
        to: Number(searchParams.get("time_to")),
      };
  return HttpResponse.json<types.CameraEvents>({
    events: cameraEvents(camera_identifier, from, to),
  });
};

export const eventsDatesOfInterestResponse = (camera_identifiers: string[]) => {
  const now = getDayjs();
  return HttpResponse.json<types.EventsDatesOfInterest>({
    dates_of_interest: Object.fromEntries(
      Array.from({ length: EVENT_DAYS + 1 }, (_, day) => {
        const date = now.subtract(day, "day").format("YYYY-MM-DD");
        const { from, to } = dayRange(date);
        return [
          date,
          {
            events: camera_identifiers.reduce(
              (total, camera_identifier) =>
                total + cameraEvents(camera_identifier, from, to).length,
              0,
            ),
            timespan_available: true,
          },
        ];
      }),
    ),
  });
};
