import { renderHook } from "@testing-library/react";
import { createRef } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useLivePlayerControls } from "components/player/liveplayer/useLivePlayerControls";
import { VideoRTC } from "components/player/liveplayer/video-rtc.js";
import * as types from "lib/types";

const { mutate } = vi.hoisted(() => ({ mutate: vi.fn() }));

vi.mock("lib/api/camera", () => ({
  useCameraManualRecording: () => ({ mutate, isPending: false }),
}));

const baseCamera: types.Camera = {
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
};

const clickManualRecording = (camera: types.Camera) => {
  const { result } = renderHook(() =>
    useLivePlayerControls(createRef<VideoRTC>(), camera),
  );
  result.current.handleManualRecording();
};

describe("useLivePlayerControls manual recording", () => {
  beforeEach(() => {
    mutate.mockClear();
  });

  it.each([
    {
      id: "no recording",
      camera: baseCamera,
      action: "start",
    },
    {
      id: "event recording in progress",
      camera: { ...baseCamera, is_recording: true },
      action: "start",
    },
    {
      id: "manual recording in progress",
      camera: { ...baseCamera, is_recording: true, is_manual_recording: true },
      action: "stop",
    },
  ])("sends $action when $id", ({ camera, action }) => {
    clickManualRecording(camera);

    expect(mutate).toHaveBeenCalledWith({ camera, action });
  });
});
