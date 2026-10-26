import { HttpResponse, http } from "msw";
import { getDayjs } from "tests/mocks/clock";
import {
  type VideoLoader,
  recordingPlaylistResponse,
  timePeriodPlaylistResponse,
} from "tests/mocks/helpers/hls";
import { mockLogs } from "tests/mocks/helpers/logs";
import {
  type TimelapseGap,
  timelapseDatesOfInterestResponse,
  timelapseFramesResponse,
  timelapseSummaryResponse,
} from "tests/mocks/helpers/timelapse";

import type {
  PtzNodesResponse,
  PtzPresetsResponse,
} from "lib/api/actions/onvif/types";
import type { LogsResponse } from "lib/api/logger";
import * as types from "lib/types";

export const API_BASE_URL = "/api/v1";

export type SnapshotLoader = (cameraIdentifier: string) => Promise<ArrayBuffer>;

export const timelapseFramesHandler = (gaps: TimelapseGap[] = []) =>
  http.get(
    `${API_BASE_URL}/timelapse/:camera_identifier`,
    ({ params, request }) => {
      const searchParams = new URL(request.url).searchParams;
      return timelapseFramesResponse(
        String(params.camera_identifier),
        Number(searchParams.get("start")),
        Number(searchParams.get("end")),
        Number(searchParams.get("max_frames") ?? 1800),
        gaps,
      );
    },
  );

export const createHandlers = (
  loadSnapshot: SnapshotLoader,
  loadVideo: VideoLoader,
) => [
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

  http.get(`${API_BASE_URL}/auth/users`, () =>
    HttpResponse.json(
      {
        users: [
          {
            id: "123456789",
            name: "Test User",
            username: "testuser",
            role: "admin",
            assigned_cameras: null,
            preferences: null,
          },
          {
            id: "223456789",
            name: "Read Only",
            username: "readonly",
            role: "read",
            assigned_cameras: ["camera1"],
            preferences: null,
          },
          {
            id: "323456789",
            name: "Writer",
            username: "writer",
            role: "write",
            assigned_cameras: ["camera2", "camera3"],
            preferences: null,
          },
        ],
      } as types.AuthUsersResponse,
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
        is_manual_recording: false,
        timelapse: true,
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
        is_manual_recording: false,
        timelapse: true,
        ptz_support: "onvif+auto",
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
        is_manual_recording: false,
        timelapse: false,
      },
    };
    return HttpResponse.json(cameras, { status: 200 });
  }),
  http.get(`${API_BASE_URL}/cameras/failed`, () =>
    HttpResponse.json({}, { status: 200 }),
  ),
  // Cameras that have stored data but are no longer configured
  http.get(`${API_BASE_URL}/cameras/orphaned`, () => {
    const orphaned: types.OrphanedCameras = {
      cameras: [
        {
          camera_identifier: "camera_3",
          file_count: 12,
          size_bytes: 2621440,
          database_rows: 4,
          directories: ["/segments/camera_3", "/event_clips/camera_3"],
        },
      ],
    };
    return HttpResponse.json(orphaned, { status: 200 });
  }),
  http.delete(
    `${API_BASE_URL}/cameras/orphaned/:camera_identifier`,
    ({ params }) => {
      const orphaned: types.OrphanedCamera = {
        camera_identifier: params.camera_identifier as string,
        file_count: 12,
        size_bytes: 2621440,
        database_rows: 4,
        directories: [],
      };
      return HttpResponse.json(orphaned, { status: 200 });
    },
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
      is_manual_recording: false,
      timelapse: true,
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
      is_manual_recording: false,
      timelapse: true,
      ptz_support: "onvif+auto",
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
      is_manual_recording: false,
      timelapse: false,
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

  http.get(`${API_BASE_URL}/events/:camera_identifier`, () =>
    HttpResponse.json<types.CameraEvents>({ events: [] }, { status: 200 }),
  ),

  http.get(
    `${API_BASE_URL}/hls/:camera_identifier/index.m3u8`,
    ({ params, request }) =>
      timePeriodPlaylistResponse(
        loadVideo,
        String(params.camera_identifier),
        Number(new URL(request.url).searchParams.get("start_timestamp")),
      ),
  ),
  http.get(
    `${API_BASE_URL}/hls/:camera_identifier/:recording_id/index.m3u8`,
    ({ params }) =>
      recordingPlaylistResponse(loadVideo, String(params.camera_identifier)),
  ),

  http.get("/files/segments/:camera/:file", async ({ params }) =>
    HttpResponse.arrayBuffer(
      await loadVideo.load(`${String(params.camera)}/${String(params.file)}`),
      {
        status: 200,
        headers: { "Content-Type": "video/mp4" },
      },
    ),
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
  // ONVIF PTZ
  http.get(`${API_BASE_URL}/actions/onvif/ptz/:camera_identifier/nodes`, () =>
    HttpResponse.json(
      {
        nodes: [
          {
            token: "PTZNodeToken",
            Name: "PTZNode",
            HomeSupported: true,
            MaximumNumberOfPresets: 255,
            SupportedPTZSpaces: {
              AbsolutePanTiltPositionSpace: [
                { XRange: { Min: -1, Max: 1 }, YRange: { Min: -1, Max: 1 } },
              ],
              ContinuousPanTiltVelocitySpace: [
                { XRange: { Min: -1, Max: 1 }, YRange: { Min: -1, Max: 1 } },
              ],
              ContinuousZoomVelocitySpace: [{ XRange: { Min: -1, Max: 1 } }],
              PanTiltSpeedSpace: [{ XRange: { Min: 0, Max: 1 } }],
              ZoomSpeedSpace: [{ XRange: { Min: 0, Max: 1 } }],
            },
          },
        ],
      } as PtzNodesResponse,
      { status: 200 },
    ),
  ),
  http.get(`${API_BASE_URL}/actions/onvif/ptz/:camera_identifier/presets`, () =>
    HttpResponse.json(
      {
        presets: [
          {
            Name: "Driveway",
            type: "onvif",
            token: "1",
            PTZPosition: { PanTilt: { x: -0.4, y: 0.1 }, Zoom: { x: 0.2 } },
          },
          {
            Name: "Front door",
            type: "onvif",
            token: "2",
            PTZPosition: { PanTilt: { x: 0.35, y: -0.05 }, Zoom: { x: 0 } },
          },
        ],
      } as PtzPresetsResponse,
      { status: 200 },
    ),
  ),
  http.all(`${API_BASE_URL}/actions/onvif/ptz/:camera_identifier/:action`, () =>
    HttpResponse.json({ success: true } as types.APISuccessResponse, {
      status: 200,
    }),
  ),

  // Timelapse
  http.get(`${API_BASE_URL}/timelapse`, () => timelapseSummaryResponse()),
  timelapseFramesHandler(),
  http.get(
    `${API_BASE_URL}/timelapse/:camera_identifier/dates_of_interest`,
    () => timelapseDatesOfInterestResponse(),
  ),
  http.get("/file/:camera_identifier/:file_key", async ({ params }) => {
    const buffer = await loadSnapshot(String(params.camera_identifier));
    return HttpResponse.arrayBuffer(buffer, {
      status: 200,
      headers: { "Content-Type": "image/jpeg" },
    });
  }),
  // Downloads of exports and rendered timelapses, nothing is actually rendered
  http.get(`${API_BASE_URL}/download`, () =>
    // Not empty, the browser only reports download progress for a body
    HttpResponse.arrayBuffer(new ArrayBuffer(1024), {
      status: 200,
      headers: { "Content-Type": "video/mp4" },
    }),
  ),
];
