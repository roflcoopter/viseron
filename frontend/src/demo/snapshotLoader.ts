import type { SnapshotLoader } from "tests/mocks/handlers";

import camera1Snapshot from "../../tests/mocks/fixtures/camera1_snapshot.jpg?url";
import camera2Snapshot from "../../tests/mocks/fixtures/camera2_snapshot.jpg?url";
import camera3Snapshot from "../../tests/mocks/fixtures/camera3_snapshot.jpg?url";

const snapshots: Record<string, string> = {
  camera1: camera1Snapshot,
  camera2: camera2Snapshot,
  camera3: camera3Snapshot,
};

export const browserSnapshotLoader: SnapshotLoader = async (
  cameraIdentifier: string,
) => {
  // Vite emits these as hashed assets. No handler matches their URLs, so MSW
  // passes the request through instead of recursing back into this loader.
  const url = snapshots[cameraIdentifier] ?? camera1Snapshot;
  const response = await fetch(url);
  return response.arrayBuffer();
};
