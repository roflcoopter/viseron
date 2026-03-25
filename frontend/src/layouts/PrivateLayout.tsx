import Container from "@mui/material/Container";
import { styled } from "@mui/material/styles";
import { Suspense, useRef } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { CSSTransition, SwitchTransition } from "react-transition-group";

import { ScrollToTopFab } from "components/ScrollToTop";
import { ErrorMessage } from "components/error/ErrorMessage";
import Footer from "components/footer/Footer";
import Header from "components/header/Header";
import { Loading } from "components/loading/Loading";
import { useAuthContext } from "context/AuthContext";
import { FullscreenProvider } from "context/FullscreenContext";
import { ViseronProvider } from "context/ViseronContext";
import { sessionExpired } from "lib/tokens";
import * as types from "lib/types";

const FullHeightContainer = styled("div")(() => ({
  minHeight: "100%",
}));

function PrivateLayoutContent() {
  const nodeRef = useRef(null);
  const location = useLocation();

  const { auth, user } = useAuthContext();

  // User is not logged in
  if (auth.enabled && !user) {
    return (
      <Navigate
        to="/login"
        state={{
          from: location.pathname,
        }}
      />
    );
  }

  // Session expired
  if (auth.enabled && sessionExpired()) {
    return (
      <Navigate
        to="/login"
        state={{
          from: location.pathname,
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

export default function PrivateLayout() {
  return (
    <FullscreenProvider>
      <PrivateLayoutContent />
    </FullscreenProvider>
  );
}

type RequireRoleProps = {
  userRole: types.AuthUserResponse["role"][];
};

export function RequireRole({ userRole }: RequireRoleProps) {
  const { auth, user } = useAuthContext();

  if (!auth.enabled) {
    return <Outlet />;
  }

  // User is not logged in
  if (!user) {
    return (
      <Navigate
        to="/login"
        state={{
          from: location.pathname,
        }}
      />
    );
  }

  if (!userRole.includes(user.role)) {
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
      </Container>
    );
  }

  return <Outlet />;
}
