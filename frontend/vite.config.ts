/// <reference types="vitest" />
/// <reference types="vite/client" />
/// <reference types="vite-plugin-svgr/client" />
import react from "@vitejs/plugin-react";
import { resolve } from "path";
import { defineConfig, loadEnv } from "vite";
import checker from "vite-plugin-checker";
import svgr from "vite-plugin-svgr";
import viteTsconfigPaths from "vite-tsconfig-paths";

const proxyOptions = {
  changeOrigin: true,
  timeout: 5000,
  proxyTimeout: 5000,
};

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  return {
    appType: "mpa",
    base: "./", // Use relative paths for assets to support any subpath
    plugins: [
      react({
        babel: {
          plugins: ["babel-plugin-react-compiler"],
        },
      }),
      viteTsconfigPaths(),
      svgr(),
      checker({
        typescript: true,
        eslint: {
          lintCommand: 'eslint \"src/**/**.{js,jsx,ts,tsx,json}\"',
          watchPath: "./src",
        },
      }),
    ],
    resolve: {
      alias: {
        // monaco-editor 0.56 remapped its `exports` so the legacy
        // `monaco-editor/esm/vs/*` paths no longer resolve. monaco-worker-manager
        // (a transitive dependency of monaco-yaml) is unmaintained and still
        // imports the old path, so map it to the current one.
        "monaco-editor/esm/vs/editor/editor.worker.js":
          "monaco-editor/editor/editor.worker.js",
      },
    },
    legacy: {
      // Vite 8 switched to Node-style CJS interop, so a default import of a
      // CommonJS package now yields `module.exports` instead of its `default`
      // property. `@jy95/material-ui-image` and `react-lazyload` are CJS-only
      // and export via `exports.default`, so they render as objects without
      // the pre-Vite 8 interop.
      inconsistentCjsInterop: true,
    },
    build: {
      rollupOptions: {
        input: {
          main: resolve(import.meta.dirname, "index.html"),
          404: resolve(import.meta.dirname, "404.html"),
        },
      },
    },
    server: {
      proxy: {
        "/api": {
          target: `http://${
            env.VITE_PROXY_HOST ? env.VITE_PROXY_HOST : "localhost:8888"
          }`,
          ...proxyOptions,
        },
        "/websocket": {
          target: `ws://${
            env.VITE_PROXY_HOST ? env.VITE_PROXY_HOST : "localhost:8888"
          }`,
          ws: true,
          ...proxyOptions,
        },
        "/files": {
          target: `http://${
            env.VITE_PROXY_HOST ? env.VITE_PROXY_HOST : "localhost:8888"
          }`,
          ...proxyOptions,
        },
        "/live": {
          target: `ws://${
            env.VITE_PROXY_HOST ? env.VITE_PROXY_HOST : "localhost:8888"
          }`,
          ...proxyOptions,
        },
        "/*/mjpeg-stream": {
          target: `http://${
            env.VITE_PROXY_HOST ? env.VITE_PROXY_HOST : "localhost:8888"
          }`,
          ...proxyOptions,
        },
      },
    },
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: "tests/setupTests.ts",
      include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
      testTimeout: 30000,
      // Disable Node's own Web Storage so jsdom owns localStorage again
      execArgv: ["--no-experimental-webstorage"],
    },
  };
});
