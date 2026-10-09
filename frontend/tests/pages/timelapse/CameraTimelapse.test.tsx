import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { Route, Routes, useLocation } from "react-router-dom";
import { API_BASE_URL } from "tests/mocks/handlers";
import { server } from "tests/mocks/server";
import { renderWithContext } from "tests/utils/renderWithContext";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { getDayjsFromUnixTimestamp } from "lib/helpers/dates";
import CameraTimelapse from "pages/timelapse/CameraTimelapse";

const NOW = 1_800_000_000;

function LocationDisplay() {
  const location = useLocation();
  return <div data-testid="location">{location.search}</div>;
}

const camera = (timelapse: boolean) => ({
  identifier: "camera1",
  name: "Camera 1",
  width: 1920,
  height: 1080,
  mainstream: { width: 1920, height: 1080 },
  timelapse,
});

let frameRequests: Record<string, string>[];

const renderPage = (search = "") =>
  renderWithContext(
    <Routes>
      <Route
        path="/timelapse/:camera_identifier"
        element={
          <>
            <CameraTimelapse />
            <LocationDisplay />
          </>
        }
      />
    </Routes>,
    { initialEntries: [`/timelapse/camera1${search}`] },
  );

const lastFrameRequest = async () => {
  await waitFor(() => expect(frameRequests.length).toBeGreaterThan(0));
  return frameRequests[frameRequests.length - 1];
};

describe("CameraTimelapse", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(NOW * 1000);
    frameRequests = [];
    server.use(
      http.get(`${API_BASE_URL}/camera/camera1`, () =>
        HttpResponse.json(camera(true)),
      ),
      http.get(`${API_BASE_URL}/timelapse/camera1`, ({ request }) => {
        const params = Object.fromEntries(new URL(request.url).searchParams);
        frameRequests.push(params);
        return HttpResponse.json({
          camera_identifier: "camera1",
          start: Number(params.start),
          end: Number(params.end),
          step: 3,
          total: 5000,
          frames: [],
          stream: null,
        });
      }),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("shows the last 24 hours up to now by default", async () => {
    renderPage();

    expect(await lastFrameRequest()).toEqual({
      start: String(NOW - 86400),
      end: String(NOW),
      max_frames: "1800",
    });
    expect(await screen.findByText("No timelapse frames in this range"));
  });

  test("a preset writes the range to the URL", async () => {
    renderPage();
    await lastFrameRequest();

    fireEvent.click(screen.getByRole("button", { name: "Yesterday" }));

    expect(screen.getByTestId("location").textContent).toBe("?range=yesterday");
    const today = getDayjsFromUnixTimestamp(NOW).startOf("day");
    await waitFor(async () =>
      expect(await lastFrameRequest()).toMatchObject({
        start: String(today.subtract(1, "day").unix()),
        end: String(today.unix()),
      }),
    );
  });

  test("a range from the URL is used as a custom range", async () => {
    renderPage("?start=1000&end=2000&frames=600");

    expect(await lastFrameRequest()).toEqual({
      start: "1000",
      end: "2000",
      max_frames: "600",
    });
    expect(screen.getByRole("button", { name: "Custom" }).className).toContain(
      "MuiChip-filled",
    );
  });

  test("changing the density keeps the range", async () => {
    renderPage("?range=today");
    await lastFrameRequest();

    fireEvent.mouseDown(screen.getByRole("combobox", { name: "Frames" }));
    fireEvent.click(await screen.findByRole("option", { name: "600" }));

    expect(screen.getByTestId("location").textContent).toBe(
      "?range=today&frames=600",
    );
  });

  test("render dialog estimates the frames from fps and length", async () => {
    renderPage();
    const renderButton = await screen.findByRole("button", {
      name: "Render Video",
    });
    await waitFor(() => expect(renderButton).toBeEnabled());

    fireEvent.click(renderButton);

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByTestId("render-estimate").textContent).toBe(
      "About 1800 frames, 1m of video",
    );
  });

  test("shows a message when the frames cannot be read", async () => {
    server.use(
      http.get(`${API_BASE_URL}/timelapse/camera1`, ({ request }) => {
        const params = Object.fromEntries(new URL(request.url).searchParams);
        return HttpResponse.json({
          camera_identifier: "camera1",
          start: Number(params.start),
          end: Number(params.end),
          step: null,
          total: 1,
          frames: [{ file_key: 1, timestamp: 1000, path: "/files/1.jpg" }],
          stream: null,
        });
      }),
    );

    renderPage();

    expect(
      await screen.findByText(
        "The timelapse frames in this range could not be read",
      ),
    ).toBeInTheDocument();
  });

  test("tells the user when timelapse is off for the camera", async () => {
    server.use(
      http.get(`${API_BASE_URL}/camera/camera1`, () =>
        HttpResponse.json(camera(false)),
      ),
    );
    renderPage();

    expect(
      await screen.findByText("Timelapse is not enabled for Camera 1"),
    ).toBeInTheDocument();
    expect(frameRequests).toEqual([]);
  });
});
