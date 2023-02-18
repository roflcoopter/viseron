import * as types from "lib/types";

export type AuthTokenData = types.AuthTokenResponse & {
  expires_at: number;
};

export const storeTokens = (tokens: types.AuthTokenResponse) => {
  const _tokens: AuthTokenData = {
    ...tokens,
    expires_at: Date.now() + tokens.expires_in * 1000,
  };
  localStorage.setItem("tokens", JSON.stringify(_tokens));
};

export const loadTokens = (): AuthTokenData => {
  const tokens = localStorage.getItem("tokens");
  return tokens !== null ? JSON.parse(tokens) : {};
};

export const clearTokens = () => {
  localStorage.removeItem("tokens");
}
