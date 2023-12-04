import dayjs, { Dayjs } from "dayjs";

import { dispatchCustomEvent } from "lib/events";
import * as types from "lib/types";

let sessionExpiredTimeout: NodeJS.Timeout | undefined;

export const clearSessionExpiredTimeout = () => {
  if (sessionExpiredTimeout) {
    clearTimeout(sessionExpiredTimeout);
    sessionExpiredTimeout = undefined;
  }
};

export const setSessionExpiredTimeout = (session_expires_at: Dayjs) => {
  if (sessionExpiredTimeout) {
    clearTimeout(sessionExpiredTimeout);
  }
  sessionExpiredTimeout = setTimeout(
    () => {
      dispatchCustomEvent("session-expired");
    },
    (session_expires_at.unix() - dayjs().unix()) * 1000,
  );
};

export const genTokens = (
  tokens: types.AuthTokenResponse,
): types.StoredTokens => ({
  ...tokens,
  expires_at: dayjs(tokens.expires_at),
  session_expires_at: dayjs(tokens.session_expires_at),
});

export const storeTokens = (tokens: types.AuthTokenResponse) => {
  localStorage.setItem("tokens", JSON.stringify(genTokens(tokens)));
};

export const loadTokens = (): types.StoredTokens | null => {
  const tokensStorage = localStorage.getItem("tokens");
  if (tokensStorage !== null) {
    const jsonTokens = JSON.parse(tokensStorage);
    const tokens = genTokens(jsonTokens);
    setSessionExpiredTimeout(tokens.session_expires_at);
    return tokens;
  }
  return null;
};

export const clearTokens = () => {
  localStorage.removeItem("tokens");
  clearSessionExpiredTimeout();
};

const expired = (expires_at: Dayjs): boolean =>
  dayjs() > expires_at.subtract(10, "seconds");

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
    return `Bearer ${storedTokens.header}.${storedTokens.payload}`;
  }
  return null;
};
