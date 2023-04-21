import { dispatchCustomEvent } from "lib/events";
import * as types from "lib/types";

let sessionExpiredTimeout: NodeJS.Timeout | undefined;

export const clearSessionExpiredTimeout = () => {
  if (sessionExpiredTimeout) {
    clearTimeout(sessionExpiredTimeout);
    sessionExpiredTimeout = undefined;
  }
};

export const setSessionExpiredTimeout = (session_expires_at: number) => {
  if (sessionExpiredTimeout) {
    clearTimeout(sessionExpiredTimeout);
  }
  sessionExpiredTimeout = setTimeout(() => {
    dispatchCustomEvent("session-expired");
  }, session_expires_at - Date.now());
};

export const storeTokens = (tokens: types.AuthTokenResponse) => {
  const _tokens: types.AuthTokenResponse = {
    ...tokens,
    expires_at: tokens.expires_at * 1000,
    session_expires_at: tokens.session_expires_at * 1000,
  };
  localStorage.setItem("tokens", JSON.stringify(_tokens));
};

export const loadTokens = (): types.AuthTokenResponse | null => {
  const tokens = localStorage.getItem("tokens");
  if (tokens !== null) {
    const jsonTokens = JSON.parse(tokens);
    setSessionExpiredTimeout(jsonTokens.session_expires_at);
    return jsonTokens;
  }
  return null;
};

export const clearTokens = () => {
  localStorage.removeItem("tokens");
  clearSessionExpiredTimeout();
};

export const tokenExpired = (): boolean => {
  const storedTokens = loadTokens();
  if (!storedTokens || Date.now() - 10000 > storedTokens.expires_at) {
    return true;
  }
  return false;
};

export const sessionExpired = (): boolean => {
  const storedTokens = loadTokens();
  if (!storedTokens || Date.now() - 10000 > storedTokens.session_expires_at) {
    return true;
  }
  return false;
};
