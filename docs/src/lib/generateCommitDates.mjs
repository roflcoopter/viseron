import fs from "fs";
import path from "path";

const ROOT =
  "src/pages/components-explorer/components";

const OUTPUT =
  "src/generated/commitDates.json";

const BASE_URL =
  "https://api.github.com/repos/roflcoopter/viseron/commits";

const headers = {
  /**
  ...(process.env.GITHUB_TOKEN
    ? { Authorization: `Bearer ${process.env.GITHUB_TOKEN}` }
    : {}),
  */
  Accept: "application/vnd.github+json",
};

/**
 * Recursively find all _meta.tsx files
 */
function findMetaFiles(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const result = [];

  for (const e of entries) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      result.push(...findMetaFiles(full));
    } else if (e.name === "_meta.tsx") {
      result.push(full);
    }
  }
  return result;
}

/**
 * Extract `path: "..."` from _meta.tsx source
 */
function extractPathFromMeta(filePath) {
  const content = fs.readFileSync(filePath, "utf8");

  const match = content.match(
    /path\s*:\s*["'`]([^"'`]+)["'`]/
  );

  return match?.[1] ?? null;
}

async function fetchCommitDates(repoPath) {
  const encoded = encodeURIComponent(repoPath);

  // latest commit
  const latestRes = await fetch(
    `${BASE_URL}?sha=master&path=${encoded}&per_page=1`,
    { headers }
  );
  const latest = await latestRes.json();
  if (!Array.isArray(latest) || latest.length === 0) {
    return null;
  }

  const updated = latest[0].commit.author.date;

  // oldest commit (paginate)
  let page = 1;
  let created = updated;

  while (true) {
    const res = await fetch(
      `${BASE_URL}?sha=master&path=${encoded}&per_page=100&page=${page}`,
      { headers }
    );
    const data = await res.json();
    if (!Array.isArray(data) || data.length === 0) break;

    created =
      data[data.length - 1].commit.author.date;

    if (data.length < 100) break;
    page++;
  }

  return { created, updated };
}

async function main() {
  const metaFiles = findMetaFiles(ROOT);
  const result = {};

  for (const file of metaFiles) {
    const repoPath = extractPathFromMeta(file);
    if (!repoPath) continue;

    result[repoPath] = await fetchCommitDates(repoPath);
  }

  fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });
  fs.writeFileSync(OUTPUT, JSON.stringify(result, null, 2));
}

main().catch(console.error);
