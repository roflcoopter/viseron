import { API_BASE_URL, createHandlers } from "tests/mocks/handlers";
import { nodeSnapshotLoader } from "tests/mocks/nodeSnapshotLoader";
import { nodeVideoLoader } from "tests/mocks/nodeVideoLoader";
import { server } from "tests/mocks/server";
import { afterEach, describe, expect, it, vi } from "vitest";

const STUB_BYTES = new Uint8Array([1, 2, 3, 4]);
const JPEG_MAGIC = new Uint8Array([0xff, 0xd8, 0xff]);

const FIXED_TIME = "2026-09-20T18:00:00Z";
const NOW = Date.parse(FIXED_TIME) / 1000;

// MSW resolves the handlers' relative paths against the jsdom origin, so
// requests have to target that same origin to be intercepted.
const url = (path: string) => `${window.location.origin}${path}`;

const snapshotUrl = (cameraIdentifier: string) =>
  url(`${API_BASE_URL}/camera/${cameraIdentifier}/snapshot`);

const stubLoader = () =>
  vi.fn(async (): Promise<ArrayBuffer> => new Uint8Array(STUB_BYTES).buffer);

// One token per segment, with "|" marking a discontinuity.
const segmentSequence = (playlist: string) =>
  Array.from(
    playlist.matchAll(
      /^#EXT-X-DISCONTINUITY$|^\/files\/segments\/camera\d\/(\d+)\.m4s$/gm,
    ),
    (match) => match[1] ?? "|",
  ).join(" ");

const allSegments = Array.from({ length: 14 }, (_, index) => index).join(" ");

describe("createHandlers", () => {
  it("serves camera snapshots from the injected loader", async () => {
    const loadSnapshot = stubLoader();
    server.use(...createHandlers(loadSnapshot, nodeVideoLoader));

    const response = await fetch(snapshotUrl("camera1"));

    expect(response.headers.get("Content-Type")).toBe("image/jpeg");
    expect(new Uint8Array(await response.arrayBuffer())).toEqual(STUB_BYTES);
    expect(loadSnapshot).toHaveBeenCalledWith("camera1");
  });

  it("serves video segments from the injected loader", async () => {
    const loadVideo = stubLoader();
    server.use(
      ...createHandlers(nodeSnapshotLoader, {
        ...nodeVideoLoader,
        load: loadVideo,
      }),
    );

    const response = await fetch(url("/files/segments/camera2/3.m4s"));

    expect(response.headers.get("Content-Type")).toBe("video/mp4");
    expect(new Uint8Array(await response.arrayBuffer())).toEqual(STUB_BYTES);
    expect(loadVideo).toHaveBeenCalledWith("camera2/3.m4s");
  });
});

describe("hls playlists", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("loops the fixture segments up until now", async () => {
    vi.stubEnv("PLAYWRIGHT_FIXED_TIME", FIXED_TIME);

    const response = await fetch(
      url(
        `${API_BASE_URL}/hls/camera1/index.m3u8?start_timestamp=${NOW - 100}`,
      ),
    );
    const body = await response.text();

    expect(response.headers.get("Content-Type")).toBe(
      "application/vnd.apple.mpegurl",
    );
    expect(segmentSequence(body)).toBe(
      "2 3 4 5 6 7 8 9 10 11 12 13 | 0 1 2 3 4 5 6 7",
    );
  });

  it.each([
    { id: "reaches now", startOffset: 3600, terminated: false },
    { id: "is capped before now", startOffset: 3 * 3600, terminated: true },
  ])(
    "only terminates a time period playlist that $id",
    async ({
      startOffset,
      terminated,
    }: {
      startOffset: number;
      terminated: boolean;
    }) => {
      vi.stubEnv("PLAYWRIGHT_FIXED_TIME", FIXED_TIME);

      const response = await fetch(
        url(
          `${API_BASE_URL}/hls/camera1/index.m3u8` +
            `?start_timestamp=${NOW - startOffset}`,
        ),
      );

      expect((await response.text()).includes("#EXT-X-ENDLIST")).toBe(
        terminated,
      );
    },
  );

  it("points each camera at its own fixture", async () => {
    vi.stubEnv("PLAYWRIGHT_FIXED_TIME", FIXED_TIME);

    const playlist = async (cameraIdentifier: string) =>
      (
        await fetch(
          url(
            `${API_BASE_URL}/hls/${cameraIdentifier}/index.m3u8` +
              `?start_timestamp=${NOW - 60}`,
          ),
        )
      ).text();

    expect(await playlist("camera3")).toContain(
      '#EXT-X-MAP:URI="/files/segments/camera3/init.mp4"',
    );
    expect(await playlist("unknown")).toContain(
      '#EXT-X-MAP:URI="/files/segments/camera1/init.mp4"',
    );
  });

  it("serves a recording as one terminated pass over the fixture", async () => {
    const response = await fetch(
      url(`${API_BASE_URL}/hls/camera1/2/index.m3u8`),
    );
    const body = await response.text();

    expect(segmentSequence(body)).toBe(allSegments);
    expect(body).toContain("#EXT-X-ENDLIST");
  });

  it("sizes the playlist by the loader's segment count", async () => {
    server.use(
      ...createHandlers(nodeSnapshotLoader, {
        ...nodeVideoLoader,
        segmentCount: () => 3,
      }),
    );

    const response = await fetch(
      url(`${API_BASE_URL}/hls/camera1/2/index.m3u8`),
    );

    expect(segmentSequence(await response.text())).toBe("0 1 2");
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

describe("nodeVideoLoader", () => {
  it("reads the init segment as a standalone mp4", async () => {
    const buffer = await nodeVideoLoader.load("camera1/init.mp4");

    expect(new TextDecoder().decode(new Uint8Array(buffer, 4, 4))).toBe("ftyp");
  });

  it("counts only the media segments of a camera fixture", () => {
    expect(nodeVideoLoader.segmentCount("camera1")).toBe(14);
  });
});
