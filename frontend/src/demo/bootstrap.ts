import { setupWorker } from "msw/browser";
import { createHandlers } from "tests/mocks/handlers";
import { wsHandlers } from "tests/mocks/wsHandlers";

import { browserSnapshotLoader } from "./snapshotLoader";

// Seed default credentials, so a visitor lands logged in.
document.cookie = "user=123456789; path=/";
localStorage.setItem(
  "camera-store",
  JSON.stringify({
    state: {
      cameras: { camera1: true, camera2: true, camera3: true },
      selectedCameras: ["camera1", "camera2", "camera3"],
      selectionOrder: ["camera1", "camera2", "camera3"],
    },
    version: 0,
  }),
);

const worker = setupWorker(
  ...createHandlers(browserSnapshotLoader),
  ...wsHandlers,
);

// Bypass keeps fonts, chunks and hashed assets flowing to the network.
await worker.start({
  onUnhandledRequest: "bypass",
  serviceWorker: { url: "./mockServiceWorker.js" },
});
