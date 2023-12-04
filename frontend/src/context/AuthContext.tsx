import { AxiosHeaders } from "axios";
import Cookies from "js-cookie";
import { FC, createContext, useLayoutEffect, useRef, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";

import SessionExpired from "components/dialog/SessionExpired";
import { Loading } from "components/loading/Loading";
import { useToast } from "hooks/UseToast";
import { authToken, useAuthEnabled } from "lib/api/auth";
import { clientId, viseronAPI } from "lib/api/client";
import { loadTokens, tokenExpired } from "lib/tokens";
import * as types from "lib/types";

export type AuthContextState = {
  auth: types.AuthEnabledResponse;
  setAuth: React.Dispatch<React.SetStateAction<AuthContextState["auth"]>>;
};

export const AuthContext = createContext<AuthContextState>({
  auth: { enabled: true, onboarding_complete: true },
  setAuth: () => {},
});

export type AuthProviderProps = {
  children: React.ReactNode;
};

let isFetchingTokens = false;
let tokenPromise: Promise<types.AuthTokenResponse>;
export const AuthProvider: FC<AuthProviderProps> = ({
  children,
}: AuthProviderProps) => {
  const [auth, setAuth] = useState<types.AuthEnabledResponse>({
    enabled: true,
    onboarding_complete: true,
  });
  const authQuery = useAuthEnabled({ setAuth });
  const toast = useToast();
  const location = useLocation();

  const requestInterceptorRef = useRef<number | undefined>(undefined);

  useLayoutEffect(() => {
    if (requestInterceptorRef.current !== undefined) {
      viseronAPI.interceptors.request.eject(requestInterceptorRef.current);
    }

    requestInterceptorRef.current = viseronAPI.interceptors.request.use(
      async (config) => {
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

        // Refresh expired token
        let storedTokens = loadTokens();
        if (
          !storedTokens ||
          (tokenExpired() && !(config as any)._tokenRefreshed)
        ) {
          if (!isFetchingTokens) {
            isFetchingTokens = true;
            tokenPromise = authToken({
              grant_type: "refresh_token",
              client_id: clientId(),
            });
          }
          const _token = await tokenPromise;
          isFetchingTokens = false;
          storedTokens = loadTokens();
          (config as any)._tokenRefreshed = true;
        }

        if (storedTokens) {
          (config.headers as AxiosHeaders).set(
            "Authorization",
            `Bearer ${storedTokens.header}.${storedTokens.payload}`,
          );
        }
        return config;
      },
    );
  }, [auth, toast]);

  if (authQuery.isInitialLoading) {
    return <Loading text="Loading Auth" />;
  }

  if (
    auth.enabled &&
    !auth.onboarding_complete &&
    location.pathname !== "/onboarding"
  ) {
    return <Navigate to="/onboarding" replace />;
  }

  return (
    <AuthContext.Provider value={{ auth, setAuth }}>
      {auth.enabled ? <SessionExpired /> : null}
      {children}
    </AuthContext.Provider>
  );
};
