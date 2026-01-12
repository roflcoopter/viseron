import { HttpResponse, http } from "msw";

import { getDayjs } from "lib/helpers/dates";
import * as types from "lib/types";

export const API_BASE_URL = "/api/v1";

export const handlers = [
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
  http.get(`${API_BASE_URL}/camera/camera*/snapshot`, () =>
    // Return an empty image
    HttpResponse.arrayBuffer(new ArrayBuffer(0), {
      status: 200,
    }),
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
];
