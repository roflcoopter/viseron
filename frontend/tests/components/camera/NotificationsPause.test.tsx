import { fireEvent, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { API_BASE_URL } from "tests/mocks/handlers";
import { server } from "tests/mocks/server";
import { renderWithContext } from "tests/utils/renderWithContext";
import { describe, expect, test } from "vitest";

import {
  AllCamerasNotificationsButton,
  CameraNotificationsButton,
  pausedUntilText,
} from "components/camera/NotificationsPause";
import * as types from "lib/types";

const camera: types.Camera = {
  identifier: "camera1",
  name: "Camera 1",
  width: 1920,
  height: 1080,
  access_token: "token",
  mainstream: { width: 1920, height: 1080 },
  still_image: {
    refresh_interval: 10,
    available: true,
    width: 1920,
    height: 1080,
  },
  failed: false,
  is_on: true,
  connected: true,
  live_stream_available: true,
  is_recording: false,
  notifications_paused: false,
  notifications_paused_until: null,
};

function captureRequests(path: string) {
  const bodies: unknown[] = [];
  server.use(
    http.post(`${API_BASE_URL}${path}`, async ({ request }) => {
      bodies.push(await request.json());
      return HttpResponse.json({ success: true });
    }),
  );
  return bodies;
}

describe("pausedUntilText", () => {
  test("describes each pause state", () => {
    expect(pausedUntilText(camera)).toBe("Pause notifications");
    expect(pausedUntilText({ ...camera, notifications_paused: true })).toBe(
      "Notifications paused until resumed",
    );
    expect(
      pausedUntilText({
        ...camera,
        notifications_paused: true,
        notifications_paused_until: new Date(
          Date.now() + 60 * 1000,
        ).toISOString(),
      }),
    ).toMatch(/^Notifications paused until .*\d{1,2}:\d{2}/);
  });
});

describe("CameraNotificationsButton", () => {
  test("pauses a camera for the chosen duration", async () => {
    const bodies = captureRequests("/camera/camera1/notifications");
    renderWithContext(<CameraNotificationsButton camera={camera} />);

    fireEvent.click(screen.getByTestId("camera-notifications-button"));
    expect(screen.queryByText("Resume notifications")).not.toBeInTheDocument();
    fireEvent.click(await screen.findByText("Pause for 1 hour"));

    await waitFor(() =>
      expect(bodies).toEqual([{ action: "pause", duration: 3600 }]),
    );
  });

  test("resumes a paused camera", async () => {
    const bodies = captureRequests("/camera/camera1/notifications");
    renderWithContext(
      <CameraNotificationsButton
        camera={{ ...camera, notifications_paused: true }}
      />,
    );

    expect(
      screen.getByLabelText("Notifications paused until resumed"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("camera-notifications-button"));
    fireEvent.click(await screen.findByText("Resume notifications"));

    await waitFor(() => expect(bodies).toEqual([{ action: "resume" }]));
  });
});

describe("AllCamerasNotificationsButton", () => {
  test("pauses every camera until resumed", async () => {
    const bodies = captureRequests("/cameras/notifications");
    renderWithContext(<AllCamerasNotificationsButton />);

    fireEvent.click(screen.getByTestId("all-cameras-notifications-button"));
    fireEvent.click(await screen.findByText("Pause until resumed"));

    await waitFor(() => expect(bodies).toEqual([{ action: "pause" }]));
  });
});
