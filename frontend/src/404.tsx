import CssBaseline from "@mui/material/CssBaseline";
import React from "react";
import { createRoot } from "react-dom/client";

import { ColorModeProvider } from "context/ColorModeContext";
import NotFound from "pages/NotFound";

import "./index.css";

// https://github.com/vitejs/vite/issues/11804
window.addEventListener("vite:preloadError", (_event) => {
  window.location.reload();
});

const container = document.getElementById("root");
const root = createRoot(container!);

root.render(
  <React.StrictMode>
    <ColorModeProvider>
      <CssBaseline enableColorScheme />
      <NotFound />
    </ColorModeProvider>
  </React.StrictMode>,
);
