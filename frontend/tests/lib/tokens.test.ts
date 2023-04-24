import { afterEach, describe, expect, test, vi } from "vitest";

import * as tokens from "lib/tokens";
import * as types from "lib/types";

const TOKENS_KEY = "tokens";
const TOKEN_DATA: types.AuthTokenResponse = {
  header: "header",
  payload: "payload",
  expires_in: 3600,
  expires_at: 3600,
  session_expires_at: 3600,
};

describe("Tokens", () => {
  const getItemSpy = vi.spyOn(Storage.prototype, "getItem");
  const setItemSpy = vi.spyOn(Storage.prototype, "setItem");
  const removeItemSpy = vi.spyOn(Storage.prototype, "removeItem");

  afterEach(() => {
    localStorage.clear();
    getItemSpy.mockClear();
    setItemSpy.mockClear();
    removeItemSpy.mockClear();
  });

  describe("loadTokens", () => {
    test("load tokens from LocalStorage", () => {
      localStorage.setItem(TOKENS_KEY, JSON.stringify(TOKEN_DATA));

      expect(tokens.loadTokens()).toStrictEqual(TOKEN_DATA);
      expect(getItemSpy).toHaveBeenCalledWith(TOKENS_KEY);
    });
  });

  describe("storeTokens", () => {
    test("store tokens in LocalStorage", () => {
      const tokenDataStored: types.AuthTokenResponse = {
        ...TOKEN_DATA,
        expires_at: TOKEN_DATA.expires_at * 1000,
        session_expires_at: TOKEN_DATA.session_expires_at * 1000,
      };

      tokens.storeTokens(TOKEN_DATA);

      expect(setItemSpy).toHaveBeenCalledWith(
        TOKENS_KEY,
        JSON.stringify(tokenDataStored)
      );
      expect(tokens.loadTokens()).toStrictEqual(tokenDataStored);
    });
  });

  describe("clearTokens", () => {
    test("clear tokens from LocalStorage", () => {
      localStorage.setItem(TOKENS_KEY, JSON.stringify(TOKEN_DATA));

      tokens.clearTokens();

      expect(removeItemSpy).toHaveBeenCalledWith(TOKENS_KEY);
      expect(tokens.loadTokens()).toBeNull();
    });
  });
});
