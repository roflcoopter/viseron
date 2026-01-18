import { InternalAxiosRequestConfig } from "axios";
import { Dayjs } from "dayjs";

import { clientId, viseronAPI } from "lib/api/client";
import { dispatchCustomEvent } from "lib/events";
import * as types from "lib/types";

import { getDayjs, getDayjsFromDateTimeString } from "./helpers/dates";

export const genTokens = (
  tokens: types.AuthTokenResponse,
): types.StoredTokens => ({
  ...tokens,
  expires_at: getDayjsFromDateTimeString(tokens.expires_at),
  session_expires_at: getDayjsFromDateTimeString(tokens.session_expires_at),
});

export const storeTokens = (tokens: types.AuthTokenResponse) => {
  localStorage.setItem("tokens", JSON.stringify(genTokens(tokens)));
};

export const loadTokens = (): types.StoredTokens | null => {
  const tokensStorage = localStorage.getItem("tokens");
  if (tokensStorage !== null) {
    const jsonTokens = JSON.parse(tokensStorage);
    const tokens = genTokens(jsonTokens);
    return tokens;
  }
  return null;
};

let isManualLogout = false;

export const setManualLogout = (value: boolean) => {
  isManualLogout = value;
};

export const isManualLogoutActive = () => isManualLogout;

let sessionExpiredTimeout: NodeJS.Timeout | undefined;
export const clearSessionExpiredTimeout = () => {
  if (sessionExpiredTimeout) {
    clearTimeout(sessionExpiredTimeout);
    sessionExpiredTimeout = undefined;
  }
};

export const setSessionExpiredTimeout = () => {
  const storedTokens = loadTokens();
  if (!storedTokens) {
    return;
  }

  if (sessionExpiredTimeout) {
    clearTimeout(sessionExpiredTimeout);
  }

  if (storedTokens.session_expires_at <= getDayjs()) {
    return;
  }

  sessionExpiredTimeout = setTimeout(
    () => {
      dispatchCustomEvent("session-expired");
    },
    (storedTokens.session_expires_at.unix() - getDayjs().unix()) * 1000,
  );
};

export const clearTokens = () => {
  localStorage.removeItem("tokens");
  clearSessionExpiredTimeout();
};

const expired = (expires_at: Dayjs): boolean =>
  getDayjs() > expires_at.subtract(10, "seconds");

export const tokenExpired = (): boolean => {
  const storedTokens = loadTokens();
  return storedTokens ? expired(storedTokens.expires_at) : true;
};

export const sessionExpired = (): boolean => {
  const storedTokens = loadTokens();
  return storedTokens ? expired(storedTokens.session_expires_at) : true;
};

export const getAuthHeader = (): string | null => {
  const storedTokens = loadTokens();
  if (storedTokens) {
    return `${storedTokens.header}.${storedTokens.payload}`;
  }
  return null;
};

interface AuthTokenVariables {
  grant_type: string;
  client_id: string;
}

export async function authToken({
  grant_type,
  client_id,
}: AuthTokenVariables): Promise<types.AuthTokenResponse> {
  const response = await viseronAPI.post("/auth/token", {
    grant_type,
    client_id,
  });
  storeTokens(response.data);
  return response.data;
}

let isFetchingTokens = false;
let tokenPromise: Promise<types.AuthTokenResponse>;
export const getToken = async (
  axiosConfig?: InternalAxiosRequestConfig<any>,
) => {
  let storedTokens = loadTokens();
  // Refresh expired token
  if (!storedTokens || tokenExpired()) {
    if (
      !isFetchingTokens &&
      (!axiosConfig || !(axiosConfig as any)._tokenRefreshed)
    ) {
      isFetchingTokens = true;
      tokenPromise = authToken({
        grant_type: "refresh_token",
        client_id: clientId(),
      });
    }
    const _token = await tokenPromise;
    isFetchingTokens = false;
    storedTokens = loadTokens();
    if (axiosConfig) {
      (axiosConfig as any)._tokenRefreshed = true;
    }
  }

  if (storedTokens) {
    return `${storedTokens.header}.${storedTokens.payload}`;
  }
  return null;
};
