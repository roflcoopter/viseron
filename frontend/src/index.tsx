import "@fontsource-variable/ibm-plex-sans";
import CssBaseline from "@mui/material/CssBaseline";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { QueryClientProvider } from "@tanstack/react-query";
import React, { Suspense } from "react";
import { createRoot } from "react-dom/client";
import { ErrorBoundary } from "react-error-boundary";
import { HashRouter as Router } from "react-router-dom";

import DemoBanner from "components/DemoBanner";
import {
  ErrorBoundaryInner,
  ErrorBoundaryOuter,
} from "components/error/ErrorMessage";
import { Loading } from "components/loading/Loading";
import ToastContainer from "components/toast/ToastContainer";
import { AuthProvider } from "context/AuthContext";
import { ColorModeProvider } from "context/ColorModeContext";
import queryClient from "lib/api/client";

import App from "./App";
import "./index.css";

// https://github.com/vitejs/vite/issues/11804
window.addEventListener("vite:preloadError", (_event) => {
  window.location.reload();
});

// Mocked demo build. Must resolve before rendering so the app's first requests
// are already intercepted.
if (import.meta.env.VITE_MOCK_API === "true") {
  await import("./demo/bootstrap");
}

const container = document.getElementById("root");
const root = createRoot(container!);

root.render(
  <React.StrictMode>
    <ErrorBoundary FallbackComponent={ErrorBoundaryOuter}>
      <ColorModeProvider>
        <LocalizationProvider dateAdapter={AdapterDayjs}>
          <CssBaseline enableColorScheme />
          <QueryClientProvider client={queryClient}>
            <Router>
              <ErrorBoundary FallbackComponent={ErrorBoundaryInner}>
                <AuthProvider>
                  <Suspense fallback={<Loading text="Loading chunk" />}>
                    <App />
                  </Suspense>
                </AuthProvider>
              </ErrorBoundary>
            </Router>
            <ToastContainer />
            <DemoBanner />
          </QueryClientProvider>
        </LocalizationProvider>
      </ColorModeProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);
