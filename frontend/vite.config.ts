/// <reference types="vitest" />
/// <reference types="vite/client" />
/// <reference types="vite-plugin-svgr/client" />
import react from "@vitejs/plugin-react";
import { resolve } from "path";
import { defineConfig, loadEnv } from "vite";
import eslint from "vite-plugin-eslint";
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
      ,
      viteTsconfigPaths(),
      svgr(),
      eslint(),
    ],
    build: {
      rollupOptions: {
        input: {
          main: resolve(__dirname, "index.html"),
          404: resolve(__dirname, "404.html"),
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
    },
  };
});
