import { createTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import { Suspense, lazy, useMemo } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

import Header from "components/header/Header";
import { Loading } from "components/loading/Loading";

const Configuration = lazy(() => import("pages/Configuration"));
const Cameras = lazy(() => import("pages/Cameras"));
const Recordings = lazy(() => import("pages/Recordings"));

function App() {
  const prefersDarkMode = useMediaQuery("(prefers-color-scheme: dark)");
  const theme = useMemo(
    () =>
      createTheme({
        palette: {
          mode: prefersDarkMode ? "dark" : "light",
        },
      }),
    [prefersDarkMode]
  );

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
      <Suspense fallback={<Loading text="Loading" />}>
        <Routes>
          <Route path="/cameras" element={<Cameras />} />
          <Route path="/recordings/:identifier" element={<Recordings />} />
          <Route path="/configuration" element={<Configuration />} />
          <Route path="/" element={<Navigate to="/cameras" replace />} />
        </Routes>
      </Suspense>
    </div>
  );
}

export default App;
