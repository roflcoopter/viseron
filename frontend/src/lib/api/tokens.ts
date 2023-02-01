export type StoreTokensParams = {
  access_token: string;
  token_type: "Bearer";
  refresh_token: string;
  expires_in: number;
};

type TokenData = {
  access_token: string;
  token_type: "Bearer";
  refresh_token: string;
  expires_in: number;
  expires_at: number;
};

export const storeTokens = (tokens: StoreTokensParams) => {
  const _tokens: TokenData = {
    ...tokens,
    expires_at: Date.now() + tokens.expires_in * 1000,
  };
  localStorage.setItem("tokens", JSON.stringify(_tokens));
};

export const loadTokens = (): TokenData => {
  const tokens = localStorage.getItem("tokens");
  return tokens !== null ? JSON.parse(tokens) : {};
};
