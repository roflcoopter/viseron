import { HttpResponse, http } from "msw";

import type { LogEntry, LogsResponse } from "lib/api/logger";
import { getDayjs } from "lib/helpers/dates";
import * as types from "lib/types";

export const API_BASE_URL = "/api/v1";

const MOCK_LOG_LINES: {
  level: LogEntry["level"];
  name: string;
  message: string;
}[] = [
  {
    level: "info",
    name: "viseron.components",
    message: "Setting up component ffmpeg",
  },
  {
    level: "debug",
    name: "viseron.components.ffmpeg.camera.camera1",
    message:
      "FFmpeg command: ffmpeg -hide_banner -loglevel error -rtsp_transport tcp " +
      "-i rtsp://***:***@192.168.1.10:554/Streaming/Channels/101",
  },
  {
    level: "info",
    name: "viseron.components.ffmpeg.camera.camera1",
    message: "Camera 1 connected, resolution 1920x1080 @ 20 FPS",
  },
  {
    level: "info",
    name: "viseron.components.darknet",
    message: "Using CUDA backend for object detection",
  },
  {
    level: "warning",
    name: "viseron.components.ffmpeg.camera.camera2",
    message: "Timeout waiting for frame, restarting camera",
  },
  {
    level: "info",
    name: "viseron.domains.motion_detector.camera2",
    message: "Motion detected, max area 0.14",
  },
  {
    level: "debug",
    name: "viseron.components.darknet.object_detector.camera2",
    message: "Objects detected: person 0.91, car 0.63",
  },
  {
    level: "info",
    name: "viseron.domains.camera.recorder.camera2",
    message: "Starting recorder for camera2, trigger type object",
  },
  {
    level: "error",
    name: "viseron.components.ffmpeg.camera.camera3",
    message: "Error starting camera: Connection refused",
  },
  {
    level: "critical",
    name: "viseron.components",
    message: "Failed to setup component edgetpu, entering safe mode",
  },
  {
    level: "debug",
    name: "viseron.components.storage.tier_handler",
    message:
      "Moving /segments/camera2/1717430400.m4s to /segments_cold/camera2",
  },
  {
    level: "info",
    name: "viseron.components.storage.tier_handler",
    message: "Tier /segments is 82% full, running cleanup",
  },
  {
    level: "info",
    name: "viseron.domains.camera.recorder.camera2",
    message: "Stopping recorder for camera2, recording id 1043",
  },
  {
    level: "info",
    name: "viseron.components.webserver",
    message: "Starting webserver on port 8888",
  },
];

// Build a log feed by repeating the sample lines, newest last, one second apart
const mockLogs = (): LogEntry[] => {
  const start = getDayjs().subtract(MOCK_LOG_LINES.length * 4, "second");
  return Array.from({ length: MOCK_LOG_LINES.length * 4 }, (_, index) => {
    const line = MOCK_LOG_LINES[index % MOCK_LOG_LINES.length];
    const timestamp = start.add(index, "second");
    return {
      id: `${timestamp.valueOf()}_${line.level}_${line.name}_${index}`,
      timestamp: timestamp.format("YYYY-MM-DD HH:mm:ss.SSS"),
      timestamp_unix_ms: timestamp.valueOf(),
      level: line.level,
      name: line.name,
      message: line.message,
      raw: `${timestamp.format("YYYY-MM-DD HH:mm:ss.SSS")} [${line.level?.toUpperCase()}] [${line.name}] - ${line.message}`,
    };
  });
};

export type SnapshotLoader = (
  cameraIdentifier: string,
) => Promise<ArrayBuffer>;

export const createHandlers = (loadSnapshot: SnapshotLoader) => [
  http.get(`${API_BASE_URL}/auth/enabled`, () =>
    HttpResponse.json(
      { enabled: true, onboarding_complete: true },
      { status: 200 },
    ),
  ),

  http.post(`${API_BASE_URL}/auth/login`, () =>
    HttpResponse.json(
      {
        header: "testheader",
        payload: "testpayload",
        expiration: 3600,
        expires_at: getDayjs().add(1, "hour").toISOString(),
        expires_at_timestamp: getDayjs().add(1, "hour").unix(),
        session_expires_at: getDayjs().add(1, "hour").toISOString(),
        session_expires_at_timestamp: getDayjs().add(1, "hour").unix(),
      } as types.AuthTokenResponse,
      { status: 200 },
    ),
  ),

  http.get(`${API_BASE_URL}/auth/user/123456789`, () =>
    HttpResponse.json(
      {
        id: "123456789",
        name: "Test User",
        username: "testuser",
        role: "admin",
        assigned_cameras: null,
        preferences: null,
      } as types.AuthUserResponse,
      { status: 200 },
    ),
  ),

  http.post(`${API_BASE_URL}/auth/token`, () => {
    const now = getDayjs().add(7, "day");
    return HttpResponse.json(
      {
        header: "testheader",
        payload: "testpayload",
        expiration: 3600,
        expires_at: now.toISOString(),
        expires_at_timestamp: now.unix(),
        session_expires_at: now.toISOString(),
        session_expires_at_timestamp: now.unix(),
      } as types.AuthTokenResponse,
      { status: 200 },
    );
  }),
  // Cameras
  http.get(`${API_BASE_URL}/cameras`, () => {
    const cameras: types.Cameras = {
      camera1: {
        identifier: "camera1",
        name: "Camera 1",
        width: 1920,
        height: 1080,
        access_token: "testtoken",
        mainstream: {
          width: 1920,
          height: 1080,
        },
        still_image: {
          refresh_interval: 5,
          available: true,
          width: 1920,
          height: 1080,
        },
        failed: false,
        is_on: true,
        live_stream_available: true,
        connected: true,
        is_recording: false,
      },
      camera2: {
        identifier: "camera2",
        name: "Camera 2",
        width: 1920,
        height: 1080,
        access_token: "testtoken",
        mainstream: {
          width: 1920,
          height: 1080,
        },
        still_image: {
          refresh_interval: 5,
          available: true,
          width: 1920,
          height: 1080,
        },
        failed: false,
        is_on: true,
        live_stream_available: true,
        connected: true,
        is_recording: true,
      },
      camera3: {
        identifier: "camera3",
        name: "Camera 3",
        width: 1920,
        height: 1080,
        access_token: "testtoken",
        mainstream: {
          width: 1920,
          height: 1080,
        },
        still_image: {
          refresh_interval: 5,
          available: true,
          width: 1920,
          height: 1080,
        },
        failed: false,
        is_on: true,
        live_stream_available: true,
        connected: true,
        is_recording: false,
      },
    };
    return HttpResponse.json(cameras, { status: 200 });
  }),
  http.get(`${API_BASE_URL}/cameras/failed`, () =>
    HttpResponse.json({}, { status: 200 }),
  ),
  // Single camera info
  http.get(`${API_BASE_URL}/camera/camera1`, () => {
    const camera: types.Camera = {
      identifier: "camera1",
      name: "Camera 1",
      width: 1920,
      height: 1080,
      access_token: "testtoken",
      mainstream: {
        width: 1920,
        height: 1080,
      },
      still_image: {
        refresh_interval: 5,
        available: true,
        width: 1920,
        height: 1080,
      },
      failed: false,
      is_on: true,
      live_stream_available: true,
      connected: true,
      is_recording: false,
    };
    return HttpResponse.json(camera, { status: 200 });
  }),
  http.get(`${API_BASE_URL}/camera/camera2`, () => {
    const camera: types.Camera = {
      identifier: "camera2",
      name: "Camera 2",
      width: 1920,
      height: 1080,
      access_token: "testtoken",
      mainstream: {
        width: 1920,
        height: 1080,
      },
      still_image: {
        refresh_interval: 5,
        available: true,
        width: 1920,
        height: 1080,
      },
      failed: false,
      is_on: true,
      live_stream_available: true,
      connected: true,
      is_recording: true,
    };
    return HttpResponse.json(camera, { status: 200 });
  }),
  http.get(`${API_BASE_URL}/camera/camera3`, () => {
    const camera: types.Camera = {
      identifier: "camera3",
      name: "Camera 3",
      width: 1920,
      height: 1080,
      access_token: "testtoken",
      mainstream: {
        width: 1920,
        height: 1080,
      },
      still_image: {
        refresh_interval: 5,
        available: true,
        width: 1920,
        height: 1080,
      },
      failed: false,
      is_on: true,
      live_stream_available: true,
      connected: true,
      is_recording: false,
    };
    return HttpResponse.json(camera, { status: 200 });
  }),
  http.get(
    `${API_BASE_URL}/camera/:camera_identifier/snapshot`,
    async ({ params }) => {
      const buffer = await loadSnapshot(String(params.camera_identifier));
      return HttpResponse.arrayBuffer(buffer, {
        status: 200,
        headers: { "Content-Type": "image/jpeg" },
      });
    },
  ),

  // Recordings list
  http.get(`${API_BASE_URL}/recordings/camera1`, () => {
    const today = getDayjs().format("YYYY-MM-DD");
    const yesterday = getDayjs().subtract(1, "day").format("YYYY-MM-DD");
    return HttpResponse.json(
      {
        [today]: {
          "2": {
            id: 2,
            camera_identifier: "camera1",
            start_time: getDayjs().subtract(1, "hour").toISOString(),
            start_timestamp: getDayjs().subtract(1, "hour").unix(),
            end_time: getDayjs().subtract(55, "minute").toISOString(),
            end_timestamp: getDayjs().subtract(55, "minute").unix(),
            trigger_type: "object",
            trigger_id: null,
            thumbnail_path: "/files/tier1/thumbnails/camera1/2.jpg",
            hls_url: "/api/v1/hls/camera1/2/index.m3u8",
          },
        },
        [yesterday]: {
          "1": {
            id: 1,
            camera_identifier: "camera1",
            start_time: getDayjs().subtract(1, "day").toISOString(),
            start_timestamp: getDayjs().subtract(1, "day").unix(),
            end_time: getDayjs()
              .subtract(1, "day")
              .add(5, "minute")
              .toISOString(),
            end_timestamp: getDayjs()
              .subtract(1, "day")
              .add(5, "minute")
              .unix(),
            trigger_type: "motion",
            trigger_id: null,
            thumbnail_path: "/files/tier1/thumbnails/camera1/1.jpg",
            hls_url: "/api/v1/hls/camera1/1/index.m3u8",
          },
        },
      } as types.RecordingsCamera,
      { status: 200 },
    );
  }),
  http.get(`${API_BASE_URL}/recordings/camera2`, () => {
    const today = getDayjs().format("YYYY-MM-DD");
    const yesterday = getDayjs().subtract(1, "day").format("YYYY-MM-DD");
    return HttpResponse.json(
      {
        [today]: {
          "4": {
            id: 4,
            camera_identifier: "camera2",
            start_time: getDayjs().subtract(1, "hour").toISOString(),
            start_timestamp: getDayjs().subtract(1, "hour").unix(),
            end_time: getDayjs().subtract(55, "minute").toISOString(),
            end_timestamp: getDayjs().subtract(55, "minute").unix(),
            trigger_type: "object",
            trigger_id: null,
            thumbnail_path: "/files/tier1/thumbnails/camera2/4.jpg",
            hls_url: "/api/v1/hls/camera2/4/index.m3u8",
          },
        },
        [yesterday]: {
          "3": {
            id: 3,
            camera_identifier: "camera2",
            start_time: getDayjs().subtract(1, "day").toISOString(),
            start_timestamp: getDayjs().subtract(1, "day").unix(),
            end_time: getDayjs()
              .subtract(1, "day")
              .add(5, "minute")
              .toISOString(),
            end_timestamp: getDayjs()
              .subtract(1, "day")
              .add(5, "minute")
              .unix(),
            trigger_type: "motion",
            trigger_id: null,
            thumbnail_path: "/files/tier1/thumbnails/camera2/3.jpg",
            hls_url: "/api/v1/hls/camera2/3/index.m3u8",
          },
        },
      } as types.RecordingsCamera,
      { status: 200 },
    );
  }),
  http.get(`${API_BASE_URL}/recordings/camera3`, () =>
    HttpResponse.json({}, { status: 200 }),
  ),

  // Profile
  http.get(`${API_BASE_URL}/profile/available_timezones`, () =>
    HttpResponse.json(
      {
        timezones: ["UTC", "America/New_York", "Europe/London", "Asia/Tokyo"],
      },
      { status: 200 },
    ),
  ),
  http.get(`${API_BASE_URL}/profile/access_tokens`, () =>
    HttpResponse.json(
      {
        access_tokens: [
          {
            id: "1",
            name: "Token 1",
            created_at: getDayjs().unix(),
            expires_at: getDayjs().add(1, "year").unix(),
            last_used_at: getDayjs().add(1234, "minutes").unix(),
            last_used_by: "testuser",
          },
        ],
      } as types.AccessTokensResponse,
      { status: 200 },
    ),
  ),
  http.put(`${API_BASE_URL}/profile/preferences`, () =>
    HttpResponse.json({}, { status: 200 }),
  ),
  http.put(`${API_BASE_URL}/profile/display_name`, () =>
    HttpResponse.json({}, { status: 200 }),
  ),

  // Tune
  http.get(`${API_BASE_URL}/tune`, () => {
    const tuneConfig: Record<string, Record<string, Record<string, any>>> = {
      camera1: {
        camera: {
          ffmpeg: {
            recorder: { idle_timeout: 10 },
          },
        },
        object_detector: {
          darknet: {
            labels: [
              {
                label: "person",
                confidence: 0.8,
                trigger_event_recording: true,
              },
              {
                label: "car",
                confidence: 0.7,
                trigger_event_recording: false,
              },
            ],
            zones: [
              {
                name: "zone1",
                coordinates: [
                  { x: 0, y: 0 },
                  { x: 100, y: 0 },
                  { x: 100, y: 100 },
                  { x: 0, y: 100 },
                ],
                labels: [{ label: "person", confidence: 0.8 }],
              },
            ],
            mask: [],
            available_labels: ["person", "car", "dog", "cat"],
          },
        },
        motion_detector: {
          mog2: {
            mask: [],
          },
        },
      },
      camera2: {
        camera: {
          ffmpeg: {
            recorder: { idle_timeout: 15 },
          },
        },
        object_detector: {
          darknet: {
            labels: [
              {
                label: "person",
                confidence: 0.9,
                trigger_event_recording: true,
              },
            ],
            zones: [],
            mask: [],
            available_labels: ["person", "car", "dog", "cat"],
          },
        },
        motion_detector: {
          mog2: {
            mask: [],
          },
        },
      },
    };
    return HttpResponse.json(tuneConfig, { status: 200 });
  }),
  http.get(`${API_BASE_URL}/tune/:camera_identifier`, ({ params }) => {
    const tuneConfigs: Record<string, Record<string, Record<string, any>>> = {
      camera1: {
        camera: {
          ffmpeg: {
            recorder: { idle_timeout: 10 },
          },
        },
        object_detector: {
          darknet: {
            labels: [
              {
                label: "person",
                confidence: 0.8,
                trigger_event_recording: true,
              },
              {
                label: "car",
                confidence: 0.7,
                trigger_event_recording: false,
              },
            ],
            zones: [
              {
                name: "zone1",
                coordinates: [
                  { x: 0, y: 0 },
                  { x: 100, y: 0 },
                  { x: 100, y: 100 },
                  { x: 0, y: 100 },
                ],
                labels: [{ label: "person", confidence: 0.8 }],
              },
            ],
            mask: [],
            available_labels: ["person", "car", "dog", "cat"],
          },
        },
        motion_detector: {
          mog2: {
            mask: [],
          },
        },
      },
      camera2: {
        camera: {
          ffmpeg: {
            recorder: { idle_timeout: 15 },
          },
        },
        object_detector: {
          darknet: {
            labels: [
              {
                label: "person",
                confidence: 0.9,
                trigger_event_recording: true,
              },
            ],
            zones: [],
            mask: [],
            available_labels: ["person", "car", "dog", "cat"],
          },
        },
        motion_detector: {
          mog2: {
            mask: [],
          },
        },
      },
      camera3: {
        camera: {
          ffmpeg: {
            recorder: { idle_timeout: 10 },
          },
        },
      },
    };
    const identifier = params.camera_identifier as string;
    const config = tuneConfigs[identifier];
    if (!config) {
      return HttpResponse.json(
        { error: `Camera '${identifier}' not found.` },
        { status: 404 },
      );
    }
    return HttpResponse.json(config, { status: 200 });
  }),
  http.put(`${API_BASE_URL}/tune/:camera_identifier`, async ({ request }) => {
    const body = (await request.json()) as {
      domain?: string;
      component?: string;
      data?: any;
    };
    if (!body.domain || !body.component) {
      return HttpResponse.json(
        { error: "Missing 'domain' or 'component' in request" },
        { status: 400 },
      );
    }
    return HttpResponse.json({ success: true }, { status: 200 });
  }),

  // Logger
  http.get(`${API_BASE_URL}/logger/logs`, ({ request }) => {
    const url = new URL(request.url);
    const lines = Number(url.searchParams.get("lines") ?? 500);
    const search = url.searchParams.get("search");
    const level = url.searchParams.get("level");

    const logs = mockLogs()
      .filter((entry) => (level ? entry.level === level : true))
      .filter((entry) =>
        search ? entry.raw.toLowerCase().includes(search.toLowerCase()) : true,
      )
      .slice(-lines);

    return HttpResponse.json(
      {
        logs,
        total_lines_returned: logs.length,
        requested_lines: lines,
        file_exists: true,
        file_size: 1048576,
        filters: { search, level },
      } as LogsResponse,
      { status: 200 },
    );
  }),
  http.get(`${API_BASE_URL}/logger/config`, () =>
    HttpResponse.json(
      {
        default_level: "info",
        logs: { "viseron.components.ffmpeg": "debug" },
        cameras: { camera2: "debug" },
      },
      { status: 200 },
    ),
  ),
];
