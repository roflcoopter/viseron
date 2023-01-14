import CssBaseline from "@mui/material/CssBaseline";
import React from "react";
import ReactDOM from "react-dom";
import { QueryClientProvider } from "react-query";
import { BrowserRouter as Router } from "react-router-dom";

import { ColorModeProvider } from "context/ColorModeContext";
import { SnackbarProvider } from "context/SnackbarContext";
import { ViseronProvider } from "context/ViseronContext";

import App from "./App";
import "./index.css";
import queryClient from "./lib/api";
import reportWebVitals from "./reportWebVitals";

ReactDOM.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <SnackbarProvider>
        <ViseronProvider>
          <ColorModeProvider>
            <CssBaseline enableColorScheme />
            <Router>
              <App />
            </Router>
          </ColorModeProvider>
        </ViseronProvider>
      </SnackbarProvider>
    </QueryClientProvider>
  </React.StrictMode>,
  document.getElementById("root")
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
