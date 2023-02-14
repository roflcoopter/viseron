import { styled, useTheme } from "@mui/material/styles";
import Cookies from "js-cookie";
import { Suspense, useContext, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

import { ScrollToTopFab } from "components/ScrollToTop";
import Footer from "components/footer/Footer";
import AppDrawer from "components/header/Drawer";
import Header from "components/header/Header";
import { Loading } from "components/loading/Loading";
import { AuthContext } from "context/AuthContext";
import { ViseronProvider } from "context/ViseronContext";
import { useAuthUser } from "lib/api/auth";
import * as types from "lib/types";

const FullHeightContainer = styled("div")(() => ({
  minHeight: "100%",
}));

function PrivateLayout() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const theme = useTheme();
  const location = useLocation();

  const { auth } = useContext(AuthContext);
  const cookies = Cookies.get();
  const [user, setUser] = useState<types.AuthUserResponse | null>(null);

  const userQuery = useAuthUser({
    username: cookies.user,
    setUser,
    configOptions: { enabled: auth.enabled && !!cookies.user },
  });

  if (userQuery.isInitialLoading || userQuery.isFetching) {
    return <Loading text="Loading" />;
  }

  if (auth.enabled && (!cookies.user || !user)) {
    return (
      <Navigate
        to="/login"
        state={{
          from: location,
          snackbarText: "Session expired, please log in again",
          snackbarType: "error",
        }}
      />
    );
  }

  return (
    <ViseronProvider>
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
        <Footer />
        <ScrollToTopFab />
      </FullHeightContainer>
    </ViseronProvider>
  );
}

export default PrivateLayout;
