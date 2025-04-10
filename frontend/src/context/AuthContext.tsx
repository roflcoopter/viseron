import { Container } from "@mui/material";
import Button from "@mui/material/Button";
import { AxiosHeaders } from "axios";
import Cookies from "js-cookie";
import { FC, createContext, useContext, useLayoutEffect, useRef } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";

import SessionExpired from "components/dialog/SessionExpired";
import { ErrorMessage } from "components/error/ErrorMessage";
import { Loading } from "components/loading/Loading";
import { useToast } from "hooks/UseToast";
import { useAuthEnabled, useAuthUser } from "lib/api/auth";
import { viseronAPI } from "lib/api/client";
import { getToken } from "lib/tokens";
import * as types from "lib/types";

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

const useAuthAxiosInterceptor = (
  auth: types.AuthEnabledResponse | undefined,
) => {
  const toast = useToast();
  const requestInterceptorRef = useRef<number | undefined>(undefined);

  useLayoutEffect(() => {
    if (requestInterceptorRef.current !== undefined) {
      viseronAPI.interceptors.request.eject(requestInterceptorRef.current);
    }

    requestInterceptorRef.current = viseronAPI.interceptors.request.use(
      async (config) => {
        // if auth is not loaded yet, allow requests to check if auth is enabled
        if (!auth && config.url?.includes("/auth/enabled")) {
          return config;
        }
        // if auth is not loaded yet, block all other requests
        if (!auth) {
          throw new Error("Request blocked, auth not loaded yet.");
        }

        // If auth is disabled, proceed without checking tokens
        if (!auth.enabled) {
          return config;
        }

        // Bypass refreshing tokens for some queries that dont require auth
        if (
          config.url?.includes("/auth/enabled") ||
          config.url?.includes("/auth/login") ||
          config.url?.includes("/onboarding")
        ) {
          return config;
        }

        const cookies = Cookies.get();
        // Safe to refresh tokens if we have a valid user cookie
        if (cookies.user && config.url?.includes("/auth/token")) {
          return config;
        }

        if (!cookies.user) {
          toast.error("Session expired, please log in again");
          throw new Error("Invalid session.");
        }

        const token = await getToken(config);
        if (token) {
          (config.headers as AxiosHeaders).set(
            "Authorization",
            `Bearer ${token}`,
          );
        }
        return config;
      },
    );

    return () => {
      if (requestInterceptorRef.current !== undefined) {
        viseronAPI.interceptors.request.eject(requestInterceptorRef.current);
      }
    };
  }, [auth, toast]);
};

type AuthContextState = {
  auth: types.AuthEnabledResponse;
  user: types.AuthUserResponse | null;
};

export const AuthContext = createContext<AuthContextState | null>(null);

type AuthProviderProps = {
  children: React.ReactNode;
};

export const AuthProvider: FC<AuthProviderProps> = ({
  children,
}: AuthProviderProps) => {
  const authQuery = useAuthEnabled();
  useAuthAxiosInterceptor(authQuery.data);
  const location = useLocation();

  const cookies = Cookies.get();
  const userQuery = useAuthUser({
    username: cookies.user,
    configOptions: {
      enabled: !!(
        authQuery.data?.enabled &&
        authQuery.data?.onboarding_complete &&
        !!cookies.user
      ),
    },
  });

  if (authQuery.isPending || authQuery.isLoading) {
    return <Loading text="Loading Auth" />;
  }

  if (authQuery.isError) {
    return (
      <ErrorMessage
        text="Error connecting to server"
        subtext={authQuery.error.message}
      />
    );
  }

  // isLoading instead of isPending because query might be disabled
  if (userQuery.isLoading) {
    return <Loading text="Loading User" />;
  }

  if (userQuery.isError) {
    return <ErrorLoadingUser />;
  }

  if (
    authQuery.data.enabled &&
    !authQuery.data.onboarding_complete &&
    location.pathname !== "/onboarding"
  ) {
    return <Navigate to="/onboarding" replace />;
  }

  return (
    <AuthContext.Provider
      value={{
        auth: authQuery.data,
        user: userQuery.data || null,
      }}
    >
      {authQuery.data.enabled ? <SessionExpired /> : null}
      {children}
    </AuthContext.Provider>
  );
};

export const useAuthContext = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuthContext must be used within AuthProvider Context");
  }
  return context;
};
