import fs from "fs";
import path from "path";
import type { Plugin } from "vite";

// The MSW worker deliberately lives outside `public/`. A service worker script
// hosted on the app origin lets any script execution on that origin install a
// permanent, origin-wide request interceptor, so it must only ever ship in the
// mocked demo build, never in a real Viseron build.
export const WORKER_DIR = "demo-public";
export const WORKER_FILE = "mockServiceWorker.js";

export const mockServiceWorkerPlugin = (
  enabled: boolean,
  rootDir: string,
): Plugin => {
  const workerPath = path.resolve(rootDir, WORKER_DIR, WORKER_FILE);

  return {
    name: "viseron:mock-service-worker",

    // Build-only hook, so the dev server never tries to emit an asset.
    generateBundle() {
      if (!enabled) {
        return;
      }

      this.emitFile({
        type: "asset",
        fileName: WORKER_FILE,
        source: fs.readFileSync(workerPath),
      });
    },

    // `vite dev` serves `public/` on its own; the worker is not in there.
    configureServer(server) {
      if (!enabled) {
        return;
      }

      server.middlewares.use((req, res, next) => {
        if (req.url?.split("?")[0] !== `/${WORKER_FILE}`) {
          next();
          return;
        }

        res.setHeader("Content-Type", "text/javascript");
        res.end(fs.readFileSync(workerPath));
      });
    },
  };
};
