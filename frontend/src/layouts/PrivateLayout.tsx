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
import * as types from "lib/types";

const FullHeightContainer = styled("div")(() => ({
  minHeight: "100%",
}));

function ErrorLoadingUser() {
  return (
    <Container
      sx={{
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        gap: 2,
      }}
    >
      <ErrorMessage text="Error loading user" />
      <Button variant="contained" component={Link} to="/login">
        Navigate to Login
      </Button>
    </Container>
  );
}

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
    return <ErrorLoadingUser />;
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

type RequireRoleProps = {
  role: types.AuthUserResponse["role"][];
};

export function RequireRole({ role }: RequireRoleProps) {
  const { auth } = useAuthContext();
  const cookies = Cookies.get();
  const userQuery = useAuthUser({
    username: cookies.user,
    configOptions: { enabled: auth.enabled && !!cookies.user },
  });

  if (!auth.enabled) {
    return <Outlet />;
  }

  // isLoading instead of isPending because query might be disabled
  if (userQuery.isLoading) {
    return <Loading text="Loading User" />;
  }
  // Failed to load user
  if (userQuery.isError) {
    return <ErrorLoadingUser />;
  }

  // User is not logged in
  if (
    (auth.enabled && (!cookies.user || !userQuery.data)) ||
    userQuery.data === undefined
  ) {
    return (
      <Navigate
        to="/login"
        state={{
          from: location,
        }}
      />
    );
  }

  if (!role.includes(userQuery.data.role)) {
    return (
      <Container
        sx={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          gap: 2,
        }}
      >
        <ErrorMessage
          text="Access Denied"
          subtext="You do not have permission to view this page."
        />
        <Button variant="contained" component={Link} to="/">
          Navigate to Home
        </Button>
      </Container>
    );
  }

  return <Outlet />;
}
