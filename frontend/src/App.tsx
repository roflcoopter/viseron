import { createTheme, styled } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

import Footer from "components/footer/Footer";
import AppDrawer from "components/header/Drawer";
import Header from "components/header/Header";
import { Loading } from "components/loading/Loading";

const Configuration = lazy(() => import("pages/Configuration"));
const Cameras = lazy(() => import("pages/Cameras"));
const Recordings = lazy(() => import("pages/Recordings"));
const Entities = lazy(() => import("pages/Entities"));

const FullHeightContainer = styled("div")(() => ({
  minHeight: "100%",
}));

const routes = [
  {
    path: "/",
    element: <Navigate to="/cameras" replace />,
  },
  {
    path: "/cameras",
    element: <Cameras />,
  },
  {
    path: "/recordings/:identifier",
    element: <Recordings />,
  },
  {
    path: "/configuration",
    element: <Configuration />,
  },
  {
    path: "/entities",
    element: <Entities />,
  },
].map(({ path, element }, key) => (
  <Route path={path} element={element} key={key} />
));

function App() {
  const [drawerOpen, setDrawerOpen] = useState(false);
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

  const [showFooter, setShowFooter] = useState(true);
  const location = useLocation();

  useEffect(() => {
    if (location.pathname === "/configuration") {
      setShowFooter(false);
      return;
    }
    setShowFooter(true);
  }, [location]);

  return (
    <FullHeightContainer>
      <FullHeightContainer>
        <AppDrawer drawerOpen={drawerOpen} setDrawerOpen={setDrawerOpen} />
        <Header setDrawerOpen={setDrawerOpen} />
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
          <Routes>{routes}</Routes>
        </Suspense>
      </FullHeightContainer>
      {showFooter && <Footer />}
    </FullHeightContainer>
  );
}

export default App;
