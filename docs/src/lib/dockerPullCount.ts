import React from "react";

import { CloudDownload } from "@carbon/icons-react";
import ExecutionEnvironment from "@docusaurus/ExecutionEnvironment";

function formatNumberShort(num: number): string {
  if (num >= 1_000_000) {
    return `${(num / 1_000_000).toFixed(num % 1_000_000 === 0 ? 0 : 1)}M`;
  }
  if (num >= 1_000) {
    return `${(num / 1_000).toFixed(num % 1_000 === 0 ? 0 : 1)}K`;
  }
  return num.toString();
}

export default formatNumberShort;

// Helper to render Download icon and count into .docker-pull-count
function renderDockerPullCount(pullCount: string, rawPullCount?: number) {
  const el = document.querySelector(".docker-pull-count");
  if (el) {
    el.innerHTML = "";
    const icon = document.createElement("span");
    icon.style.display = "inline-flex";
    icon.style.verticalAlign = "middle";
    // Tooltip text
    let tooltip = "Total Docker pulls";
    if (rawPullCount !== undefined) {
      tooltip += `: ${rawPullCount.toLocaleString()}`;
    }
    (el as HTMLElement).title = tooltip;
    // Render React icon to string and inject
    import("react-dom/client").then((ReactDOMClient) => {
      const root = ReactDOMClient.createRoot(icon);
      root.render(
        React.createElement(CloudDownload, {
          size: 14,
          style: { marginRight: 4, verticalAlign: "middle" },
        }),
      );
      el.appendChild(icon);
      const text = document.createElement("span");
      text.textContent = pullCount;
      text.style.fontWeight = "600";
      text.style.fontSize = "14px";
      el.appendChild(text);
    });
  }
}

let cachedPullCount: string | null = null;
let cachedRawPullCount: number | undefined;

function ensureDockerPullCount() {
  const el = document.querySelector(".docker-pull-count");
  if (el && cachedPullCount) {
    // Only inject if not already injected
    if (!el.querySelector("span")) {
      renderDockerPullCount(cachedPullCount, cachedRawPullCount);
    }
  }
}

if (ExecutionEnvironment.canUseDOM) {
  fetch(
    "https://proxy.corsfix.com/?https://hub.docker.com/v2/repositories/roflcoopter/viseron",
    {
      headers: {
        Origin: "http://localhost:3000", // this will bypass CORS
        Referer: "http://localhost:3000", // same as above
      },
    },
  )
    .then((response) => response.json())
    .then((data) => {
      cachedPullCount = formatNumberShort(data.pull_count) || "100K+";
      cachedRawPullCount = data.pull_count;
      ensureDockerPullCount();
    })
    .catch(() => {
      cachedPullCount = "100K+"; // Fallback value on error
      cachedRawPullCount = 100000;
      ensureDockerPullCount();
    });

  // Observe DOM changes to re-inject badge if needed (SPA navigation)
  const observer = new MutationObserver(() => {
    ensureDockerPullCount();
  });
  observer.observe(document.body, { childList: true, subtree: true });
}
