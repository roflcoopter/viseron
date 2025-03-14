import Button from "@mui/material/Button";
import Container from "@mui/material/Container";
import { styled } from "@mui/material/styles";
import Cookies from "js-cookie";
import { Suspense, useRef } from "react";
import { Link, Navigate, Outlet, useLocation } from "react-router-dom";
import { CSSTransition, SwitchTransition } from "react-transition-group";

import { ScrollToTopFab } from "components/ScrollToTop";
import { ErrorMessage } from "components/error/ErrorMessage";
import Footer from "components/footer/Footer";
import Header from "components/header/Header";
import { Loading } from "components/loading/Loading";
import { useAuthContext } from "context/AuthContext";
import { ViseronProvider } from "context/ViseronContext";
import { toastIds, useToast } from "hooks/UseToast";
import { useAuthUser } from "lib/api/auth";
import { sessionExpired } from "lib/tokens";

const FullHeightContainer = styled("div")(() => ({
  minHeight: "100%",
}));

export default function PrivateLayout() {
  const nodeRef = useRef(null);
  const location = useLocation();

  const { auth } = useAuthContext();
  const cookies = Cookies.get();
  const toast = useToast();

  const userQuery = useAuthUser({
    username: cookies.user,
    configOptions: { enabled: auth.enabled && !!cookies.user },
  });

  // isLoading instead of isPending because query might be disabled
  if (userQuery.isLoading) {
    return <Loading text="Loading User" />;
  }

  // Failed to load user
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
        <ErrorMessage
          text="Error loading user"
          subtext={userQuery.error.message}
        />
        <Button variant="contained" component={Link} to="/login">
          Navigate to Login
        </Button>
      </Container>
    );
  }

  // User is not logged in
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

  // Session expired
  if (auth.enabled && sessionExpired()) {
    toast.warning("Session expired, please log in again", {
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
          <Header />
          <Suspense fallback={<Loading text="Loading" />}>
            <SwitchTransition>
              <CSSTransition
                key={location.pathname}
                appear
                in
                nodeRef={nodeRef}
                timeout={200}
                classNames="page"
                unmountOnExit
              >
                <div ref={nodeRef}>
                  <Outlet />
                </div>
              </CSSTransition>
            </SwitchTransition>
          </Suspense>
        </FullHeightContainer>
        <Footer />
        <ScrollToTopFab />
      </FullHeightContainer>
    </ViseronProvider>
  );
}
