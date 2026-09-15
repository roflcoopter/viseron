import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { describe, expect, it } from "vitest";

import {
  WORKER_DIR,
  WORKER_FILE,
  mockServiceWorkerPlugin,
} from "../../vite-plugins/mockServiceWorker";

const frontendRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);

interface EmittedAsset {
  type: string;
  fileName: string;
  source: Uint8Array;
}

type Middleware = (
  req: { url?: string },
  res: {
    setHeader: (name: string, value: string) => void;
    end: (body: unknown) => void;
  },
  next: () => void,
) => void;

// The plugin's only outputs are the assets it hands to Rollup and the
// middleware it hands to the dev server, so drive those hooks directly.
const collectEmittedAssets = (enabled: boolean): EmittedAsset[] => {
  const emitted: EmittedAsset[] = [];
  const plugin = mockServiceWorkerPlugin(enabled, frontendRoot);
  const generateBundle = plugin.generateBundle as unknown as (this: {
    emitFile: (asset: EmittedAsset) => string;
  }) => void;

  generateBundle.call({
    emitFile: (asset) => {
      emitted.push(asset);
      return "ref";
    },
  });

  return emitted;
};

const collectMiddleware = (enabled: boolean): Middleware | undefined => {
  let registered: Middleware | undefined;
  const plugin = mockServiceWorkerPlugin(enabled, frontendRoot);
  const configureServer = plugin.configureServer as unknown as (server: {
    middlewares: { use: (middleware: Middleware) => void };
  }) => void;

  configureServer({
    middlewares: {
      use: (middleware) => {
        registered = middleware;
      },
    },
  });

  return registered;
};

describe("mockServiceWorkerPlugin", () => {
  it("emits nothing when demo mode is disabled", () => {
    expect(collectEmittedAssets(false)).toEqual([]);
  });

  it("emits the worker at the site root when demo mode is enabled", () => {
    const expected = fs.readFileSync(
      path.resolve(frontendRoot, WORKER_DIR, WORKER_FILE),
    );

    const emitted = collectEmittedAssets(true);

    expect(emitted).toHaveLength(1);
    expect(emitted[0].fileName).toBe(WORKER_FILE);
    expect(Buffer.from(emitted[0].source)).toEqual(expected);
  });

  it("registers no dev middleware when demo mode is disabled", () => {
    expect(collectMiddleware(false)).toBeUndefined();
  });

  it("serves the worker as javascript from the dev server when enabled", () => {
    const middleware = collectMiddleware(true);
    const headers: Record<string, string> = {};
    let body: unknown;
    let nextCalled = false;

    middleware!(
      { url: `/${WORKER_FILE}` },
      {
        setHeader: (name, value) => {
          headers[name] = value;
        },
        end: (chunk) => {
          body = chunk;
        },
      },
      () => {
        nextCalled = true;
      },
    );

    expect(nextCalled).toBe(false);
    expect(headers["Content-Type"]).toBe("text/javascript");
    expect(Buffer.from(body as Uint8Array)).toEqual(
      fs.readFileSync(path.resolve(frontendRoot, WORKER_DIR, WORKER_FILE)),
    );
  });

  it("passes unrelated dev server requests through", () => {
    const middleware = collectMiddleware(true);
    let nextCalled = false;

    middleware!(
      { url: "/index.html" },
      { setHeader: () => {}, end: () => {} },
      () => {
        nextCalled = true;
      },
    );

    expect(nextCalled).toBe(true);
  });
});
