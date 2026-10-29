import { setupServer } from "msw/node";

import { createHandlers } from "./handlers.js";
import { nodeSnapshotLoader } from "./nodeSnapshotLoader.js";
import { nodeVideoLoader } from "./nodeVideoLoader.js";

export const server = setupServer(
  ...createHandlers(nodeSnapshotLoader, nodeVideoLoader),
);
