import CssBaseline from "@mui/material/CssBaseline";
import { QueryClientProvider } from "@tanstack/react-query";
import React, { Suspense } from "react";
import ReactDOM from "react-dom";
import { HashRouter as Router } from "react-router-dom";
import { ToastContainer } from "react-toastify";

import { Loading } from "components/loading/Loading";
import { AuthProvider } from "context/AuthContext";
import { ColorModeProvider } from "context/ColorModeContext";

import App from "./App";
import "./index.css";
import queryClient from "./lib/api/client";

ReactDOM.render(
  <React.StrictMode>
    <ColorModeProvider>
      <CssBaseline enableColorScheme />
      <QueryClientProvider client={queryClient}>
        <Router>
          <AuthProvider>
            <Suspense fallback={<Loading text="Loading chunk" />}>
              <App />
            </Suspense>
          </AuthProvider>
        </Router>
        <ToastContainer
          position="bottom-left"
          pauseOnFocusLoss={false}
          autoClose={5000}
          draggablePercent={50}
          theme="colored"
        />
      </QueryClientProvider>
    </ColorModeProvider>
  </React.StrictMode>,
  document.getElementById("root")
);
