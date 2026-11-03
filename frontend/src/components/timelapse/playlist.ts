import { API_V1_URL } from "lib/api/client";
import * as types from "lib/types";

// The middle of a frame, so that seeking never lands on the previous one
export const frameTime = (index: number, fps: number) => (index + 0.5) / fps;

export const frameAt = (time: number, fps: number) => Math.floor(time * fps);

export const isBuffered = (ranges: TimeRanges, time: number) =>
  Array.from({ length: ranges.length }, (_, i) => i).some(
    (i) => time >= ranges.start(i) && time <= ranges.end(i),
  );

export function frameIndexAtOrAfter(
  frames: types.TimelapseFrame[],
  timestamp: number,
) {
  const index = frames.findIndex((frame) => frame.timestamp >= timestamp);
  return index === -1 ? Math.max(frames.length - 1, 0) : index;
}

function segmentUrl(
  camera_identifier: string,
  frames: types.TimelapseFrame[],
  startFrame: number,
  stream: types.TimelapseStream,
) {
  const params = new URLSearchParams({
    keys: frames.map((frame) => frame.file_key.toString(16)).join(","),
    start_frame: String(startFrame),
    width: String(stream.width),
    height: String(stream.height),
  });
  // Absolute since the playlist is loaded from a blob URL
  return `${window.location.origin}${API_V1_URL}/timelapse/${camera_identifier}/segment?${params}`;
}

/**
 * Build a VOD playlist where each segment is encoded by the server from the
 * frames named in its URL, so the segments always match the frame list.
 */
export function buildTimelapsePlaylist(
  camera_identifier: string,
  frames: types.TimelapseFrame[],
  stream: types.TimelapseStream,
) {
  const lines = [
    "#EXTM3U",
    "#EXT-X-VERSION:3",
    `#EXT-X-TARGETDURATION:${Math.ceil(stream.segment_frames / stream.fps)}`,
    "#EXT-X-MEDIA-SEQUENCE:0",
    "#EXT-X-PLAYLIST-TYPE:VOD",
  ];
  for (let start = 0; start < frames.length; start += stream.segment_frames) {
    const segment = frames.slice(start, start + stream.segment_frames);
    lines.push(
      `#EXTINF:${(segment.length / stream.fps).toFixed(3)},`,
      segmentUrl(camera_identifier, segment, start, stream),
    );
  }
  lines.push("#EXT-X-ENDLIST");
  return lines.join("\n");
}
