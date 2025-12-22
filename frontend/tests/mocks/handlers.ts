import dayjs from "dayjs";
import utc from "dayjs/plugin/utc.js";
import { HttpResponse, http } from "msw";

import * as types from "lib/types";

dayjs.extend(utc);
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
        expires_at: dayjs().add(1, "hour").toISOString(),
        expires_at_timestamp: dayjs().add(1, "hour").unix(),
        session_expires_at: dayjs().add(1, "hour").toISOString(),
        session_expires_at_timestamp: dayjs().add(1, "hour").unix(),
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
      },
      { status: 200 },
    ),
  ),

  http.post(`${API_BASE_URL}/auth/token`, () => {
    const now = dayjs().add(7, "day");
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
        access_token: "testtoken1",
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
      },
      camera2: {
        identifier: "camera2",
        name: "Camera 2",
        width: 1920,
        height: 1080,
        access_token: "testtoken2",
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
      },
    };
    return HttpResponse.json(cameras, { status: 200 });
  }),
  http.get(`${API_BASE_URL}/cameras/failed`, () => {
    const cameras: types.FailedCameras = {
      camera3: {
        identifier: "camera3",
        name: "Camera 3",
        width: 1920,
        height: 1080,
        mainstream: {
          width: 1920,
          height: 1080,
        },
        live_stream_available: true,
        error: "Camera not found",
        retrying: true,
        failed: true,
      },
    };
    return HttpResponse.json(cameras, { status: 200 });
  }),
  // Single camera info
  http.get(`${API_BASE_URL}/camera/camera1`, () => {
    const camera: types.Camera = {
      identifier: "camera1",
      name: "Camera 1",
      width: 1920,
      height: 1080,
      access_token: "testtoken1",
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
    };
    return HttpResponse.json(camera, { status: 200 });
  }),
  http.get(`${API_BASE_URL}/camera/camera2`, () => {
    const camera: types.Camera = {
      identifier: "camera2",
      name: "Camera 2",
      width: 1920,
      height: 1080,
      access_token: "testtoken2",
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
    };
    return HttpResponse.json(camera, { status: 200 });
  }),
];
