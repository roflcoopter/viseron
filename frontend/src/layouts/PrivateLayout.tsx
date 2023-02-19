import { styled } from "@mui/material/styles";
import Cookies from "js-cookie";
import { Suspense, useContext, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import "react-toastify/dist/ReactToastify.css";

import { ScrollToTopFab } from "components/ScrollToTop";
import Footer from "components/footer/Footer";
import AppDrawer from "components/header/Drawer";
import Header from "components/header/Header";
import { Loading } from "components/loading/Loading";
import { AuthContext } from "context/AuthContext";
import { ViseronProvider } from "context/ViseronContext";
import { useToast } from "hooks/UseToast";
import { useAuthUser } from "lib/api/auth";
import queryClient from "lib/api/client";
import * as types from "lib/types";

const FullHeightContainer = styled("div")(() => ({
  minHeight: "100%",
}));

export default function PrivateLayout() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const location = useLocation();

  const { auth } = useContext(AuthContext);
  const cookies = Cookies.get();
  const [user, setUser] = useState<types.AuthUserResponse | null>(null);
  const toast = useToast();

  const userQuery = useAuthUser({
    username: cookies.user,
    setUser,
    configOptions: { enabled: auth.enabled && !!cookies.user },
  });

  // isInitialLoading instead of isLoading because query might be disabled
  if (userQuery.isInitialLoading) {
    return <Loading text="Loading User" />;
  }

  if (auth.enabled && (!cookies.user || !user)) {
    queryClient.removeQueries();
    toast.error("Session expired, please log in again");
    return (
      <Navigate
        to="/login"
        state={{
          from: location,
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
