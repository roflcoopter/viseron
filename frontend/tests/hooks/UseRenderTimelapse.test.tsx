import { act } from "@testing-library/react";
import { renderHookWithContext } from "tests/utils/renderWithContext";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useRenderTimelapse } from "hooks/UseRenderTimelapse";
import { downloadFile } from "lib/api/download";
import { renderTimelapse } from "lib/commands";
import * as types from "lib/types";

vi.mock("lib/commands", async (importOriginal) => ({
  ...(await importOriginal<typeof import("lib/commands")>()),
  renderTimelapse: vi.fn(),
}));
vi.mock("lib/api/download", () => ({ downloadFile: vi.fn() }));
const toastMock = vi.hoisted(() =>
  Object.assign(vi.fn(), {
    isActive: vi.fn(),
    update: vi.fn(),
    dismiss: vi.fn(),
  }),
);
vi.mock("react-toastify", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react-toastify")>()),
  toast: toastMock,
}));

const PARAMS = { camera_identifier: "camera1", start: 0, end: 3600 };
const DONE: types.TimelapseRenderStatus = {
  status: "done",
  filename: "camera1-timelapse.mp4",
  token: "token",
};

type StatusCallback = (status: types.TimelapseRenderStatus) => Promise<void>;
type ErrorCallback = (
  message: types.WebSocketSubscriptionErrorResponse,
) => void;

// Captures the callbacks the hook registers and lets tests acknowledge the command
const mockRender = () => {
  const server = {
    onStatus: undefined as unknown as StatusCallback,
    onError: undefined as unknown as ErrorCallback,
    cancel: vi.fn(async () => {}),
    acknowledge: () => {},
    reject: (_error: unknown) => {},
  };
  vi.mocked(renderTimelapse).mockImplementation(
    (_connection, _params, onStatus, onError) =>
      new Promise((resolve, reject) => {
        server.onStatus = onStatus as StatusCallback;
        server.onError = onError;
        server.acknowledge = () => resolve(server.cancel);
        server.reject = reject;
      }),
  );
  return server;
};

const renderRenderHook = () =>
  renderHookWithContext(() => useRenderTimelapse(), {
    connection: {} as any,
  });

describe("useRenderTimelapse", () => {
  beforeEach(() => {
    vi.mocked(renderTimelapse).mockReset();
    vi.mocked(downloadFile).mockReset();
    toastMock.mockReset();
    toastMock.isActive.mockReset();
    toastMock.update.mockReset();
    toastMock.dismiss.mockReset();
  });

  it("follows the render status and downloads the result", async () => {
    const server = mockRender();
    let resolveDownload: (downloaded: boolean) => void = () => {};
    vi.mocked(downloadFile).mockReturnValue(
      new Promise((resolve) => {
        resolveDownload = resolve;
      }),
    );
    const { result } = renderRenderHook();

    let started: Promise<void>;
    act(() => {
      started = result.current.start(PARAMS);
    });
    expect(result.current.state).toEqual({ status: "starting" });
    await act(async () => {
      server.acknowledge();
      await started;
    });
    expect(renderTimelapse).toHaveBeenCalledWith(
      expect.anything(),
      PARAMS,
      expect.any(Function),
      expect.any(Function),
    );

    const rendering: types.TimelapseRenderStatus = {
      status: "rendering",
      frame: 5,
      total_frames: 10,
      progress: 50,
    };
    await act(async () => {
      server.onStatus(rendering);
    });
    expect(result.current.state).toEqual(rendering);

    let finished: Promise<void>;
    act(() => {
      finished = server.onStatus(DONE);
    });
    expect(result.current.state).toEqual({ status: "downloading" });
    expect(downloadFile).toHaveBeenCalledWith(
      DONE,
      expect.stringContaining("timelapse-render-camera1"),
      "camera1",
    );

    await act(async () => {
      resolveDownload(true);
      await finished;
    });
    expect(result.current.state).toEqual({ status: "done" });
  });

  it("reports a failed download", async () => {
    const server = mockRender();
    vi.mocked(downloadFile).mockResolvedValue(false);
    const { result } = renderRenderHook();

    await act(async () => {
      const started = result.current.start(PARAMS);
      server.acknowledge();
      await started;
      await server.onStatus(DONE);
    });

    expect(result.current.state).toEqual({
      status: "error",
      error: "Download failed",
    });
  });

  it.each([
    {
      name: "the command is rejected",
      fail: (server: ReturnType<typeof mockRender>) =>
        server.reject({ code: "not_found", message: "Not found" }),
      error: "Not found",
    },
    {
      name: "the render fails",
      fail: (server: ReturnType<typeof mockRender>) => {
        server.acknowledge();
        server.onError({
          command_id: 1,
          type: "subscription_result",
          success: false,
          error: { code: "unknown_error", message: "ffmpeg failed" },
        });
      },
      error: "ffmpeg failed",
    },
  ])("shows the error when $name", async ({ fail, error }) => {
    const server = mockRender();
    const { result } = renderRenderHook();

    await act(async () => {
      const started = result.current.start(PARAMS);
      fail(server);
      await started;
    });

    expect(result.current.state).toEqual({ status: "error", error });
  });

  it("cancels a running render and ignores later status", async () => {
    const server = mockRender();
    const { result } = renderRenderHook();
    await act(async () => {
      const started = result.current.start(PARAMS);
      server.acknowledge();
      await started;
    });

    await act(async () => {
      await result.current.cancel();
      server.onStatus({ status: "encoding" });
    });

    expect(server.cancel).toHaveBeenCalledOnce();
    expect(result.current.state).toEqual({ status: "cancelled" });
  });

  it("cancels once the server acknowledges the command", async () => {
    const server = mockRender();
    const { result } = renderRenderHook();

    let started: Promise<void>;
    await act(async () => {
      started = result.current.start(PARAMS);
      await result.current.cancel();
    });
    expect(server.cancel).not.toHaveBeenCalled();

    await act(async () => {
      server.acknowledge();
      await started;
    });

    expect(server.cancel).toHaveBeenCalledOnce();
    expect(result.current.state).toEqual({ status: "cancelled" });
  });

  it("does not cancel while downloading", async () => {
    const server = mockRender();
    vi.mocked(downloadFile).mockReturnValue(new Promise(() => {}));
    const { result } = renderRenderHook();
    await act(async () => {
      const started = result.current.start(PARAMS);
      server.acknowledge();
      await started;
      server.onStatus(DONE);
    });

    await act(async () => {
      await result.current.cancel();
    });

    expect(server.cancel).not.toHaveBeenCalled();
    expect(result.current.state).toEqual({ status: "downloading" });
  });

  it("ignores start while a render is running and allows it again after", async () => {
    const server = mockRender();
    const { result } = renderRenderHook();
    await act(async () => {
      const started = result.current.start(PARAMS);
      server.acknowledge();
      await started;
      await result.current.start(PARAMS);
    });
    expect(renderTimelapse).toHaveBeenCalledOnce();

    await act(async () => {
      await result.current.cancel();
    });
    act(() => {
      result.current.reset();
    });
    expect(result.current.state).toEqual({ status: "idle" });

    mockRender();
    act(() => {
      result.current.start(PARAMS);
    });
    expect(renderTimelapse).toHaveBeenCalledTimes(2);
  });

  it("moves the progress into a toast while hidden", async () => {
    const server = mockRender();
    const { result } = renderRenderHook();
    await act(async () => {
      const started = result.current.start(PARAMS);
      server.acknowledge();
      await started;
      await server.onStatus({
        status: "rendering",
        frame: 1,
        total_frames: 2,
        progress: 50,
      });
    });
    expect(toastMock).not.toHaveBeenCalled();

    act(() => {
      result.current.hide();
    });
    expect(toastMock).toHaveBeenCalledWith(
      "camera1: Rendering timelapse... 50%",
      expect.objectContaining({ type: "info", autoClose: false }),
    );
    const { toastId } = toastMock.mock.calls[0][1];

    toastMock.isActive.mockReturnValue(true);
    await act(async () => {
      await server.onStatus({ status: "encoding" });
    });
    expect(toastMock.update).toHaveBeenCalledWith(
      toastId,
      expect.objectContaining({ render: "camera1: Encoding timelapse..." }),
    );

    act(() => {
      result.current.show();
    });
    expect(toastMock.dismiss).toHaveBeenCalledWith(toastId);
  });

  it("finishes the hidden toast when the download is done", async () => {
    const server = mockRender();
    vi.mocked(downloadFile).mockResolvedValue(true);
    toastMock.isActive.mockReturnValue(true);
    const { result } = renderRenderHook();
    await act(async () => {
      const started = result.current.start(PARAMS);
      server.acknowledge();
      await started;
    });
    act(() => {
      result.current.hide();
    });

    await act(async () => {
      await server.onStatus(DONE);
    });

    expect(toastMock.update).toHaveBeenLastCalledWith(
      expect.any(String),
      expect.objectContaining({
        render: "camera1: Timelapse downloaded",
        type: "success",
        autoClose: 5000,
      }),
    );
  });
});
