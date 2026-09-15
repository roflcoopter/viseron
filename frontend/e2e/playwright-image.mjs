// Prints the Playwright container image matching the pinned @playwright/test
// version, e.g. mcr.microsoft.com/playwright:v1.62.1-noble.
//
// This is used to have a consistent environment when both
// generating and comparing screenshots
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const lockPath = fileURLToPath(
  new URL("../package-lock.json", import.meta.url),
);
const { packages } = JSON.parse(readFileSync(lockPath, "utf8"));
const version = packages?.["node_modules/@playwright/test"]?.version;

if (!version) {
  throw new Error(
    "@playwright/test is missing from frontend/package-lock.json, cannot resolve the Playwright image",
  );
}

process.stdout.write(`mcr.microsoft.com/playwright:v${version}-noble\n`);
