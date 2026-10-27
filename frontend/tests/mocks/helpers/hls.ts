import { HttpResponse } from "msw";
import { getDayjs } from "tests/mocks/clock";

export interface VideoLoader {
  load: (file: string) => Promise<ArrayBuffer>;
  segmentCount: (camera: string) => number;
}

const SEGMENT_DURATION = 5;
const VIDEO_FIXTURE_CAMERAS = ["camera1", "camera2", "camera3"];

// Unknown cameras fall back to camera1's footage, like the snapshots do.
const videoFixtureCamera = (cameraIdentifier: string) =>
  VIDEO_FIXTURE_CAMERAS.includes(cameraIdentifier)
    ? cameraIdentifier
    : VIDEO_FIXTURE_CAMERAS[0];

// HLS playlist that loops the fixture segments from `from` to `to`.
// Each loop restarts the media timestamps so it is preceded by a
// discontinuity tag
const hlsPlaylistResponse = (
  loadVideo: VideoLoader,
  cameraIdentifier: string,
  from: number,
  to: number,
  end: boolean,
) => {
  const camera = videoFixtureCamera(cameraIdentifier);
  const segmentCount = loadVideo.segmentCount(camera);
  const segments = `/files/segments/${camera}`;
  const first = from - (from % SEGMENT_DURATION);
  const lines = [
    "#EXTM3U",
    "#EXT-X-VERSION:6",
    "#EXT-X-MEDIA-SEQUENCE:0",
    `#EXT-X-TARGETDURATION:${SEGMENT_DURATION}`,
    "#EXT-X-INDEPENDENT-SEGMENTS",
    `#EXT-X-MAP:URI="${segments}/init.mp4"`,
  ];
  for (
    let timestamp = first;
    timestamp + SEGMENT_DURATION <= to;
    timestamp += SEGMENT_DURATION
  ) {
    const segment = (timestamp / SEGMENT_DURATION) % segmentCount;
    if (segment === 0 && timestamp !== first) {
      lines.push("#EXT-X-DISCONTINUITY");
    }
    lines.push(
      `#EXT-X-PROGRAM-DATE-TIME:${new Date(timestamp * 1000).toISOString()}`,
      `#EXTINF:${SEGMENT_DURATION},`,
      `${segments}/${segment}.m4s`,
    );
  }
  if (end) {
    lines.push("#EXT-X-ENDLIST");
  }
  return new HttpResponse(lines.join("\n"), {
    status: 200,
    headers: { "Content-Type": "application/vnd.apple.mpegurl" },
  });
};

export const timePeriodPlaylistResponse = (
  loadVideo: VideoLoader,
  cameraIdentifier: string,
  from: number,
) => {
  const now = getDayjs().unix();
  const to = Math.min(now, from + 2 * 3600);
  return hlsPlaylistResponse(loadVideo, cameraIdentifier, from, to, to < now);
};

// The recording player ignores program date times, so a single pass over the
// fixture is enough.
export const recordingPlaylistResponse = (
  loadVideo: VideoLoader,
  cameraIdentifier: string,
) =>
  hlsPlaylistResponse(
    loadVideo,
    cameraIdentifier,
    0,
    loadVideo.segmentCount(videoFixtureCamera(cameraIdentifier)) *
      SEGMENT_DURATION,
    true,
  );
