import { QueryClient } from "@tanstack/react-query";
import { screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { API_BASE_URL } from "tests/mocks/handlers";
import { server } from "tests/mocks/server";
import { renderWithContext } from "tests/utils/renderWithContext";
import { describe, expect, test } from "vitest";

import AppDrawer from "components/header/Drawer";
import Timelapse from "pages/timelapse/Timelapse";

const camera = (identifier: string, timelapse: boolean) => ({
  identifier,
  name: `Camera ${identifier}`,
  width: 1920,
  height: 1080,
  mainstream: { width: 1920, height: 1080 },
  timelapse,
});

const mockCameras = (timelapse: Record<string, boolean>) =>
  server.use(
    http.get(`${API_BASE_URL}/cameras`, () =>
      HttpResponse.json(
        Object.fromEntries(
          Object.entries(timelapse).map(([identifier, enabled]) => [
            identifier,
            camera(identifier, enabled),
          ]),
        ),
      ),
    ),
    http.get(`${API_BASE_URL}/timelapse`, () =>
      HttpResponse.json({
        cameras: {
          front: {
            camera_identifier: "front",
            count: 42,
            first_timestamp: 1000,
            last_timestamp: 4600,
            latest_frame: {
              file_key: 1,
              timestamp: 4600,
              path: "/files/front/4600.jpg",
            },
          },
        },
      }),
    ),
  );

describe("Timelapse", () => {
  test("lists the cameras with timelapse enabled", async () => {
    mockCameras({ front: true, back: false });
    renderWithContext(<Timelapse />);

    expect(await screen.findByText("Camera front")).toBeInTheDocument();
    expect(screen.queryByText("Camera back")).not.toBeInTheDocument();
    expect(screen.getByText("42 frames")).toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAttribute(
      "src",
      "/files/front/4600.jpg",
    );
    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      "/timelapse/front",
    );
  });

  test("explains how to enable timelapse when no camera has it", async () => {
    mockCameras({ front: false });
    renderWithContext(<Timelapse />);

    expect(
      await screen.findByText("Timelapse is not enabled for any camera"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open Documentation" }),
    ).toBeInTheDocument();
  });

  test.each<{
    name: string;
    timelapse: Record<string, boolean>;
    shown: boolean;
  }>([
    { name: "shows", timelapse: { front: true, back: false }, shown: true },
    { name: "hides", timelapse: { front: false }, shown: false },
  ])("drawer $name the timelapse link", async ({ timelapse, shown }) => {
    mockCameras(timelapse);
    const queryClient = new QueryClient();
    renderWithContext(<AppDrawer drawerOpen setDrawerOpen={() => {}} />, {
      queryClient,
    });

    await waitFor(() =>
      expect(queryClient.getQueryData(["cameras"])).toBeDefined(),
    );

    expect(!!screen.queryByText("Timelapse")).toBe(shown);
  });
});
