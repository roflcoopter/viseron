import { renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { server } from "tests/mocks/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useMjpegStreamMultipart } from "components/player/mjpegplayer/useMjpegStreamMultipart";

const STREAM_URL = "http://localhost/camera1/mjpeg-stream";
const FRAME = new Uint8Array([0xff, 0xd8, 0x01, 0x02, 0xff, 0xd9]);

const multipartBody = () => {
  const encoder = new TextEncoder();
  return new Uint8Array([
    ...encoder.encode(
      `--jpgboundary\r\nContent-type: image/jpeg\r\nContent-Length: ${FRAME.length}\r\n\r\n`,
    ),
    ...FRAME,
    ...encoder.encode("\r\n--jpgboundary--\r\n"),
  ]);
};

describe("useMjpegStreamMultipart", () => {
  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => "blob:frame");
    URL.revokeObjectURL = vi.fn();
  });

  it("requests an octet-stream response and renders its frames", async () => {
    const accept = vi.fn();
    server.use(
      http.get(STREAM_URL, ({ request }) => {
        accept(request.headers.get("Accept"));
        return new HttpResponse(multipartBody(), {
          headers: { "Content-Type": "application/octet-stream" },
        });
      }),
    );
    const img = document.createElement("img");

    const { result } = renderHook(() =>
      useMjpegStreamMultipart({ current: img }, STREAM_URL),
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.error).toBeNull();
    expect(accept).toHaveBeenCalledWith("application/octet-stream");
    expect(img.src).toBe("blob:frame");
  });
});
