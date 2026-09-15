import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

import type { SnapshotLoader } from "./handlers.js";

export const nodeSnapshotLoader: SnapshotLoader = async (
  cameraIdentifier: string,
) => {
  const dirname = path.dirname(fileURLToPath(import.meta.url));
  const imagePath = path.resolve(
    dirname,
    `fixtures/${cameraIdentifier}_snapshot.jpg`,
  );
  const buffer = fs.readFileSync(imagePath);
  // Buffer instances share a pooled ArrayBuffer, so copy into an exactly sized
  // one rather than handing out the whole pool.
  return new Uint8Array(buffer).buffer;
};
