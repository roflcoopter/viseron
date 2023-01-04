import CssBaseline from "@mui/material/CssBaseline";
import React from "react";
import ReactDOM from "react-dom";
import { QueryClientProvider } from "react-query";
import { BrowserRouter as Router } from "react-router-dom";

import { ColorModeProvider } from "context/ColorModeContext";
import { ViseronProvider } from "context/ViseronContext";

import App from "./App";
import "./index.css";
import queryClient from "./lib/api";
import reportWebVitals from "./reportWebVitals";

ReactDOM.render(
  <React.StrictMode>
    <ViseronProvider>
      <ColorModeProvider>
        <CssBaseline enableColorScheme />
        <Router>
          <QueryClientProvider client={queryClient}>
            <App />
          </QueryClientProvider>
        </Router>
      </ColorModeProvider>
    </ViseronProvider>
  </React.StrictMode>,
  document.getElementById("root")
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
