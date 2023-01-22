import { styled, useTheme } from "@mui/material/styles";
import { Suspense, useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

import { ScrollToTopFab } from "components/ScrollToTop";
import Footer from "components/footer/Footer";
import AppDrawer from "components/header/Drawer";
import Header from "components/header/Header";
import { Loading } from "components/loading/Loading";

const FullHeightContainer = styled("div")(() => ({
  minHeight: "100%",
}));

function PrivateLayout() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const theme = useTheme();
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
          <Outlet />
        </Suspense>
      </FullHeightContainer>
      {showFooter && <Footer />}
      <ScrollToTopFab />
    </FullHeightContainer>
  );
}

export default PrivateLayout;
