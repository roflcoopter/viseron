import CssBaseline from "@mui/material/CssBaseline";
import React from "react";
import ReactDOM from "react-dom";

import { ColorModeProvider } from "context/ColorModeContext";
import NotFound from "pages/NotFound";

import "./index.css";

ReactDOM.render(
  <React.StrictMode>
    <ColorModeProvider>
      <CssBaseline enableColorScheme />
      <NotFound />
    </ColorModeProvider>
  </React.StrictMode>,
  document.getElementById("root"),
);
