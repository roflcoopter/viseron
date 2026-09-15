import { API_BASE_URL, createHandlers } from "tests/mocks/handlers";
import { nodeSnapshotLoader } from "tests/mocks/nodeSnapshotLoader";
import { server } from "tests/mocks/server";
import { describe, expect, it, vi } from "vitest";

const STUB_BYTES = new Uint8Array([1, 2, 3, 4]);
const JPEG_MAGIC = new Uint8Array([0xff, 0xd8, 0xff]);

// MSW resolves the handlers' relative paths against the jsdom origin, so
// requests have to target that same origin to be intercepted.
const snapshotUrl = (cameraIdentifier: string) =>
  `${window.location.origin}${API_BASE_URL}/camera/${cameraIdentifier}/snapshot`;

describe("createHandlers", () => {
  it("serves camera snapshots from the injected loader", async () => {
    const loadSnapshot = vi.fn(
      async (): Promise<ArrayBuffer> => new Uint8Array(STUB_BYTES).buffer,
    );
    server.use(...createHandlers(loadSnapshot));

    const response = await fetch(snapshotUrl("camera1"));

    expect(response.headers.get("Content-Type")).toBe("image/jpeg");
    expect(new Uint8Array(await response.arrayBuffer())).toEqual(STUB_BYTES);
    expect(loadSnapshot).toHaveBeenCalledWith("camera1");
  });
});

describe("nodeSnapshotLoader", () => {
  it("reads the fixture as a standalone jpeg", async () => {
    const buffer = await nodeSnapshotLoader("camera1");

    // Buffer instances share a pooled ArrayBuffer, so an unsliced `.buffer`
    // would start with unrelated bytes instead of the JPEG magic number.
    expect(new Uint8Array(buffer).slice(0, 3)).toEqual(JPEG_MAGIC);
  });
});
