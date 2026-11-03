import type { VideoLoader } from "tests/mocks/helpers/hls";

const FIXTURE_DIR = "../../tests/mocks/fixtures/video/";

// Vite emits these as hashed assets. No handler matches their URLs, so MSW
// passes the request through instead of recursing back into this loader.
const fixtures = import.meta.glob<string>(
  "../../tests/mocks/fixtures/video/*/*",
  {
    query: "?url",
    import: "default",
    eager: true,
  },
);

export const browserVideoLoader: VideoLoader = {
  load: async (file: string) => {
    const response = await fetch(fixtures[`${FIXTURE_DIR}${file}`]);
    return response.arrayBuffer();
  },
  segmentCount: (camera: string) => {
    const prefix = `${FIXTURE_DIR}${camera}/`;
    return Object.keys(fixtures).filter(
      (file) =>
        file.startsWith(prefix) && /^\d+\.m4s$/.test(file.slice(prefix.length)),
    ).length;
  },
};
