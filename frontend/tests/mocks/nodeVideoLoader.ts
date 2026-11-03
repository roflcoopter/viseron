import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

import type { VideoLoader } from "./helpers/hls.js";

const FIXTURE_DIR = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "fixtures/video",
);

export const nodeVideoLoader: VideoLoader = {
  load: async (file: string) => {
    const buffer = fs.readFileSync(path.resolve(FIXTURE_DIR, file));
    return new Uint8Array(buffer).buffer;
  },
  segmentCount: (camera: string) =>
    fs
      .readdirSync(path.resolve(FIXTURE_DIR, camera))
      .filter((file) => /^\d+\.m4s$/.test(file)).length,
};
