import { fireEvent, screen } from "@testing-library/react";
import { renderWithContext } from "tests/utils/renderWithContext";
import { describe, expect, it, vi } from "vitest";

import { LivePlayer } from "components/player/liveplayer/LivePlayer";
import * as types from "lib/types";

vi.mock("screenfull", () => ({
  default: { isEnabled: false, on: vi.fn(), off: vi.fn() },
}));

vi.mock("components/player/liveplayer/video-stream.js", () => ({}));

const camera: types.Camera = {
  width: 1920,
  height: 1080,
  identifier: "camera1",
  name: "Camera 1",
  access_token: "token",
  mainstream: {
    width: 1920,
    height: 1080,
  },
  still_image: {
    refresh_interval: 0,
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
};

describe("LivePlayer fullscreen", () => {
  it("toggles player fullscreen without the Fullscreen API", () => {
    const onPlayerFullscreenChange = vi.fn();
    renderWithContext(
      <LivePlayer
        camera={camera}
        src="/live?src=camera1"
        onPlayerFullscreenChange={onPlayerFullscreenChange}
      />,
    );
    const container = screen.getByRole("button", { name: "Video player" });
    fireEvent.touchStart(container);

    fireEvent.click(screen.getByRole("button", { name: "Fullscreen" }));

    expect(onPlayerFullscreenChange).toHaveBeenLastCalledWith(true);

    fireEvent.click(screen.getByRole("button", { name: "Exit fullscreen" }));

    expect(onPlayerFullscreenChange).toHaveBeenLastCalledWith(false);
    expect(container).toHaveStyle({ position: "relative" });
  });
});
