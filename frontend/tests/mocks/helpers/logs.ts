import { getDayjs } from "tests/mocks/clock";

import type { LogEntry } from "lib/api/logger";

const MOCK_LOG_LINES: {
  level: LogEntry["level"];
  name: string;
  message: string;
}[] = [
  {
    level: "info",
    name: "viseron.components",
    message: "Setting up component ffmpeg",
  },
  {
    level: "debug",
    name: "viseron.components.ffmpeg.camera.camera1",
    message:
      "FFmpeg command: ffmpeg -hide_banner -loglevel error -rtsp_transport tcp " +
      "-i rtsp://***:***@192.168.1.10:554/Streaming/Channels/101",
  },
  {
    level: "info",
    name: "viseron.components.ffmpeg.camera.camera1",
    message: "Camera 1 connected, resolution 1920x1080 @ 20 FPS",
  },
  {
    level: "info",
    name: "viseron.components.darknet",
    message: "Using CUDA backend for object detection",
  },
  {
    level: "warning",
    name: "viseron.components.ffmpeg.camera.camera2",
    message: "Timeout waiting for frame, restarting camera",
  },
  {
    level: "info",
    name: "viseron.domains.motion_detector.camera2",
    message: "Motion detected, max area 0.14",
  },
  {
    level: "debug",
    name: "viseron.components.darknet.object_detector.camera2",
    message: "Objects detected: person 0.91, car 0.63",
  },
  {
    level: "info",
    name: "viseron.domains.camera.recorder.camera2",
    message: "Starting recorder for camera2, trigger type object",
  },
  {
    level: "error",
    name: "viseron.components.ffmpeg.camera.camera3",
    message: "Error starting camera: Connection refused",
  },
  {
    level: "critical",
    name: "viseron.components",
    message: "Failed to setup component edgetpu, entering safe mode",
  },
  {
    level: "debug",
    name: "viseron.components.storage.tier_handler",
    message:
      "Moving /segments/camera2/1717430400.m4s to /segments_cold/camera2",
  },
  {
    level: "info",
    name: "viseron.components.storage.tier_handler",
    message: "Tier /segments is 82% full, running cleanup",
  },
  {
    level: "info",
    name: "viseron.domains.camera.recorder.camera2",
    message: "Stopping recorder for camera2, recording id 1043",
  },
  {
    level: "info",
    name: "viseron.components.webserver",
    message: "Starting webserver on port 8888",
  },
];

// Build a log feed by repeating the sample lines, newest last, one second apart
export const mockLogs = (): LogEntry[] => {
  const start = getDayjs().subtract(MOCK_LOG_LINES.length * 4, "second");
  return Array.from({ length: MOCK_LOG_LINES.length * 4 }, (_, index) => {
    const line = MOCK_LOG_LINES[index % MOCK_LOG_LINES.length];
    const timestamp = start.add(index, "second");
    return {
      id: `${timestamp.valueOf()}_${line.level}_${line.name}_${index}`,
      timestamp: timestamp.format("YYYY-MM-DD HH:mm:ss.SSS"),
      timestamp_unix_ms: timestamp.valueOf(),
      level: line.level,
      name: line.name,
      message: line.message,
      raw: `${timestamp.format("YYYY-MM-DD HH:mm:ss.SSS")} [${line.level?.toUpperCase()}] [${line.name}] - ${line.message}`,
    };
  });
};
