import ExecutionEnvironment from "@docusaurus/ExecutionEnvironment";

// This code runs in the browser
if (ExecutionEnvironment.canUseDOM) {
  // Fetch latest version from GitHub Releases API
  fetch("https://api.github.com/repos/roflcoopter/viseron/releases/latest")
    .then((response) => response.json())
    .then((data) => {
      const version = data.tag_name || "unknown";

      // Inject version into CSS content
      const style = document.createElement("style");
      style.innerHTML = `
        .navbar__title::after {
          content: "${version}" !important;
        }
      `;
      document.head.appendChild(style);
    });
}

export default function injectVersion() {
  // This function is required but can be empty
  // The code above runs on module load
}
