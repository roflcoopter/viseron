import CssBaseline from "@mui/material/CssBaseline";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { QueryClientProvider } from "@tanstack/react-query";
import React, { Suspense } from "react";
import ReactDOM from "react-dom";
import { HashRouter as Router } from "react-router-dom";

import { Loading } from "components/loading/Loading";
import ToastContainer from "components/toast/ToastContainer";
import { AuthProvider } from "context/AuthContext";
import { ColorModeProvider } from "context/ColorModeContext";
import queryClient from "lib/api/client";

import App from "./App";
import "./index.css";

ReactDOM.render(
  <React.StrictMode>
    <ColorModeProvider>
      <LocalizationProvider dateAdapter={AdapterDayjs}>
        <CssBaseline enableColorScheme />
        <QueryClientProvider client={queryClient}>
          <Router>
            <AuthProvider>
              <Suspense fallback={<Loading text="Loading chunk" />}>
                <App />
              </Suspense>
            </AuthProvider>
          </Router>
          <ToastContainer />
        </QueryClientProvider>
      </LocalizationProvider>
    </ColorModeProvider>
  </React.StrictMode>,
  document.getElementById("root"),
);
