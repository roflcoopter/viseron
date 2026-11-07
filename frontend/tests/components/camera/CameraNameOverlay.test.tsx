import { screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { API_BASE_URL } from "tests/mocks/handlers";
import { server } from "tests/mocks/server";
import { renderWithContext } from "tests/utils/renderWithContext";
import { describe, expect, test } from "vitest";

import { CameraNameOverlay } from "components/camera/CameraNameOverlay";
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
  is_manual_recording: false,
  timelapse: false,
  notifications_configured: true,
  notifications_paused: true,
  notifications_paused_until: null,
};

const adminUser: types.AuthUserResponse = {
  id: "1",
  name: "",
  username: "",
  role: "admin",
  assigned_cameras: null,
  preferences: null,
};

const readUser: types.AuthUserResponse = { ...adminUser, role: "read" };

function mockCamera(overrides: Partial<types.Camera> = {}) {
  server.use(
    http.get(`${API_BASE_URL}/camera/camera1`, () =>
      HttpResponse.json({ ...camera, ...overrides }),
    ),
  );
}

describe("CameraNameOverlay notifications", () => {
  test("shows the pause toggle when asked to", async () => {
    mockCamera();
    renderWithContext(
      <CameraNameOverlay camera_identifier="camera1" notificationsPause />,
      { user: adminUser },
    );

    expect(
      await screen.findByTestId("camera-notifications-button"),
    ).toHaveAccessibleName("Notifications paused until resumed");
  });

  test("shows the pause as text without the toggle", async () => {
    mockCamera();
    renderWithContext(<CameraNameOverlay camera_identifier="camera1" />);

    expect(
      await screen.findByText("Notifications paused until resumed"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("camera-notifications-button"),
    ).not.toBeInTheDocument();
  });

  test("shows the pause as text to a user who is not an admin", async () => {
    mockCamera();
    renderWithContext(
      <CameraNameOverlay camera_identifier="camera1" notificationsPause />,
      { user: readUser },
    );

    expect(
      await screen.findByText("Notifications paused until resumed"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("camera-notifications-button"),
    ).not.toBeInTheDocument();
  });

  test("shows no toggle for a camera without notifications", async () => {
    mockCamera({
      notifications_configured: false,
      notifications_paused: false,
    });
    renderWithContext(
      <CameraNameOverlay camera_identifier="camera1" notificationsPause />,
      { user: adminUser },
    );

    expect(await screen.findByText("Camera 1")).toBeInTheDocument();
    expect(
      screen.queryByTestId("camera-notifications-button"),
    ).not.toBeInTheDocument();
  });
});
