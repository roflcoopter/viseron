import { Container } from "@mui/material";
import Button from "@mui/material/Button";
import { AxiosHeaders } from "axios";
import Cookies from "js-cookie";
import {
  createContext,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Link, Navigate, useLocation } from "react-router-dom";

import SessionExpired from "components/dialog/SessionExpired";
import { ErrorMessage } from "components/error/ErrorMessage";
import { Loading } from "components/loading/Loading";
import { useToast } from "hooks/UseToast";
import { useAuthEnabled, useAuthUser } from "lib/api/auth";
import { viseronAPI } from "lib/api/client";
import { dayjsSetDefaultTimezone, getDefaultTimezone } from "lib/helpers/dates";
import { getToken, isManualLogoutActive } from "lib/tokens";
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
  user: types.AuthUserResponse | null,
) => {
  const toast = useToast();
  const requestInterceptorRef = useRef<number | undefined>(undefined);
  const sessionErrorShownRef = useRef(false);

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
          if (
            !sessionErrorShownRef.current &&
            !isManualLogoutActive() &&
            user !== null
          ) {
            sessionErrorShownRef.current = true;
            toast.error("Session expired, please log in again");
          }
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
  }, [auth, toast, user]);
};

// Sync user cookie with state to trigger re-renders
const useUserCookieSync = () => {
  const [cookiesUser, setCookiesUser] = useState(Cookies.get("user"));

  useEffect(() => {
    const checkCookie = () => {
      const currentCookie = Cookies.get("user");
      setCookiesUser(currentCookie);
    };
    checkCookie();

    const interval = setInterval(checkCookie, 100);

    return () => clearInterval(interval);
  }, [setCookiesUser]);

  return cookiesUser;
};

type AuthContextState = {
  auth: types.AuthEnabledResponse;
  user: types.AuthUserResponse | null;
};

export const AuthContext = createContext<AuthContextState | null>(null);

type AuthProviderProps = {
  children: React.ReactNode;
};

export function AuthProvider({ children }: AuthProviderProps) {
  const authQuery = useAuthEnabled();
  const location = useLocation();
  const cookiesUser = useUserCookieSync();

  const userQuery = useAuthUser({
    username: cookiesUser || "",
    configOptions: {
      enabled: !!(
        authQuery.data?.enabled &&
        authQuery.data?.onboarding_complete &&
        !!cookiesUser
      ),
    },
  });

  useAuthAxiosInterceptor(authQuery.data, userQuery.data ?? null);

  const authContextState = useMemo<AuthContextState>(
    () => ({
      auth: authQuery.data!,
      user: userQuery.data ?? null,
    }),
    [authQuery.data, userQuery.data],
  );

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
  // Skip loading screen during manual logout to avoid flash
  if (userQuery.isLoading && !isManualLogoutActive()) {
    return <Loading text="Loading User" />;
  }

  // Don't show error if we're on login page or if there's no cookie (user just logged out)
  if (userQuery.isError && cookiesUser && location.pathname !== "/login") {
    return <ErrorLoadingUser />;
  }

  if (
    authQuery.data.enabled &&
    !authQuery.data.onboarding_complete &&
    location.pathname !== "/onboarding"
  ) {
    return <Navigate to="/onboarding" replace />;
  }

  if (!authQuery.data) {
    return (
      <ErrorMessage
        text="Error loading auth"
        subtext="Auth context value is null"
      />
    );
  }

  // Set global timezone based on user preference
  const userTimezone =
    userQuery.data?.preferences?.timezone ??
    Intl.DateTimeFormat().resolvedOptions().timeZone;
  if (getDefaultTimezone() !== userTimezone) {
    dayjsSetDefaultTimezone(userTimezone);
  }

  return (
    <AuthContext.Provider value={authContextState}>
      {authQuery.data.enabled ? <SessionExpired /> : null}
      {children}
    </AuthContext.Provider>
  );
}

export const useAuthContext = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuthContext must be used within AuthProvider Context");
  }
  return context;
};
