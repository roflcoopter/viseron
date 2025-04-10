import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
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
];
