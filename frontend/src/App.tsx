// import logo from "./logo.svg";
import { createTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import * as React from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

import Header from "components/header/Header";
import Cameras from "pages/Cameras";
import Configuration from "pages/Configuration";
import Recordings from "pages/Recordings";

function App() {
  const prefersDarkMode = useMediaQuery("(prefers-color-scheme: dark)");
  const theme = React.useMemo(
    () =>
      createTheme({
        palette: {
          mode: prefersDarkMode ? "dark" : "light",
        },
      }),
    [prefersDarkMode]
  );

  const location = useLocation();

  React.useEffect(() => {
    // Cancel mjpeg stream requests when navigating away from /cameras.
    if (location.pathname === "/cameras") {
      return;
    }
    window.stop();
  }, [location]);

  return (
    <div>
      <Header />
      <ToastContainer
        position="bottom-left"
        autoClose={5000}
        hideProgressBar={false}
        newestOnTop={false}
        closeOnClick
        rtl={false}
        pauseOnFocusLoss
        draggable
        pauseOnHover
        theme={theme.palette.mode}
      />

      <Routes>
        <Route path="/cameras" element={<Cameras />} />
        <Route path="/recordings/:identifier" element={<Recordings />} />
        <Route path="/configuration" element={<Configuration />} />
        <Route path="/" element={<Navigate to="/cameras" replace />} />
      </Routes>
    </div>
  );
}

export default App;
