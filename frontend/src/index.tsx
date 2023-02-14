import CssBaseline from "@mui/material/CssBaseline";
import { QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom";
import { BrowserRouter as Router } from "react-router-dom";

import { AuthProvider } from "context/AuthContext";
import { ColorModeProvider } from "context/ColorModeContext";
import { SnackbarProvider } from "context/SnackbarContext";

import App from "./App";
import "./index.css";
import queryClient from "./lib/api/client";
import reportWebVitals from "./reportWebVitals";

ReactDOM.render(
  <React.StrictMode>
    <ColorModeProvider>
      <CssBaseline enableColorScheme />
      <QueryClientProvider client={queryClient}>
        <SnackbarProvider>
          <Router>
            <AuthProvider>
              <App />
            </AuthProvider>
          </Router>
        </SnackbarProvider>
      </QueryClientProvider>
    </ColorModeProvider>
  </React.StrictMode>,
  document.getElementById("root")
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
