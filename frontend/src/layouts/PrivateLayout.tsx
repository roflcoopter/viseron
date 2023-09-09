import Button from "@mui/material/Button";
import Container from "@mui/material/Container";
import { styled } from "@mui/material/styles";
import Cookies from "js-cookie";
import { Suspense, useContext, useEffect, useState } from "react";
import { Link, Navigate, Outlet, useLocation } from "react-router-dom";
import CSSTransition from "react-transition-group/CSSTransition";
import TransitionGroup from "react-transition-group/TransitionGroup";

import { ScrollToTopFab } from "components/ScrollToTop";
import { Error } from "components/error/Error";
import Footer from "components/footer/Footer";
import AppDrawer from "components/header/Drawer";
import Header from "components/header/Header";
import { Loading } from "components/loading/Loading";
import { AuthContext } from "context/AuthContext";
import { ViseronProvider } from "context/ViseronContext";
import { toastIds, useToast } from "hooks/UseToast";
import { useAuthUser } from "lib/api/auth";
import { sessionExpired } from "lib/tokens";
import * as types from "lib/types";

const FullHeightContainer = styled("div")(() => ({
  minHeight: "100%",
}));

export default function PrivateLayout() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const location = useLocation();

  const { auth } = useContext(AuthContext);
  const cookies = Cookies.get();
  const [_user, setUser] = useState<types.AuthUserResponse | undefined>(
    undefined
  );
  const toast = useToast();

  const userQuery = useAuthUser({
    username: cookies.user,
    setUser,
    configOptions: { enabled: auth.enabled && !!cookies.user },
  });

  useEffect(() => {
    setUser(userQuery.data);
  }, [userQuery.data]);

  // isInitialLoading instead of isLoading because query might be disabled
  if (userQuery.isInitialLoading) {
    return <Loading text="Loading User" />;
  }

  if (userQuery.isError) {
    toast.error("Failed to load user", {
      toastId: toastIds.userLoadError,
    });
    return (
      <Container
        sx={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          gap: 2,
          height: "100vh",
        }}
      >
        <Error text="Error loading user" />
        <Button variant="contained" component={Link} to="/login">
          Navigate to Login
        </Button>
      </Container>
    );
  }
  if (auth.enabled && (!cookies.user || !userQuery.data)) {
    return (
      <Navigate
        to="/login"
        state={{
          from: location,
        }}
      />
    );
  }

  if (auth.enabled && sessionExpired()) {
    toast.error("Session expired, please log in again", {
      toastId: toastIds.sessionExpired,
    });
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
            <TransitionGroup>
              <CSSTransition
                key={location.key}
                timeout={1000}
                classNames="page"
              >
                <Outlet />
              </CSSTransition>
            </TransitionGroup>
          </Suspense>
        </FullHeightContainer>
        <Footer />
        <ScrollToTopFab />
      </FullHeightContainer>
    </ViseronProvider>
  );
}
