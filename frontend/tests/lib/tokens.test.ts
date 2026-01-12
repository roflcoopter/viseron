import { afterEach, describe, expect, test, vi } from "vitest";

import { getDayjs } from "lib/helpers/dates";
import * as tokens from "lib/tokens";
import * as types from "lib/types";

const TOKENS_KEY = "tokens";

const NOW = getDayjs();
const TOKEN_RESPONSE: types.AuthTokenResponse = {
  header: "header",
  payload: "payload",
  expiration: 3600,
  expires_at: NOW.add(3600, "second").toISOString(),
  expires_at_timestamp: NOW.add(3600, "second").unix(),
  session_expires_at: NOW.add(3600, "second").toISOString(),
  session_expires_at_timestamp: NOW.add(3600, "second").unix(),
};

const TOKEN_DATA: types.StoredTokens = {
  header: "header",
  payload: "payload",
  expiration: 3600,
  expires_at: NOW.add(3600, "second"),
  expires_at_timestamp: NOW.add(3600, "second").unix(),
  session_expires_at: NOW.add(3600, "second"),
  session_expires_at_timestamp: NOW.add(3600, "second").unix(),
};

vi.useFakeTimers();

describe("Tokens", () => {
  const getItemSpy = vi.spyOn(Storage.prototype, "getItem");
  const setItemSpy = vi.spyOn(Storage.prototype, "setItem");
  const removeItemSpy = vi.spyOn(Storage.prototype, "removeItem");

  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.setItem(TOKENS_KEY, JSON.stringify(TOKEN_DATA));
  });

  afterEach(() => {
    vi.useRealTimers();
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
      tokens.storeTokens(TOKEN_RESPONSE);

      expect(setItemSpy).toHaveBeenCalledWith(
        TOKENS_KEY,
        JSON.stringify(TOKEN_DATA),
      );
      expect(tokens.loadTokens()).toStrictEqual(TOKEN_DATA);
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

  describe("tokenExpired", () => {
    test("token is flagged as expired", () => {
      tokens.storeTokens(TOKEN_RESPONSE);
      vi.advanceTimersByTime(3601 * 1000);
      const expired = tokens.tokenExpired();
      expect(expired).toBe(true);
    });

    test("token is flagged as expired when it has less than 10 seconds left to live", () => {
      const _tokens = {
        ...TOKEN_DATA,
        expires_at: getDayjs().add(9, "seconds").toISOString(),
        expires_at_timestamp: getDayjs().add(9, "seconds").unix(),
        session_expires_at: getDayjs().add(9, "seconds").toISOString(),
        session_expires_at_timestamp: getDayjs().add(9, "seconds").unix(),
      };
      tokens.storeTokens(_tokens);
      const expired = tokens.tokenExpired();
      expect(expired).toBe(true);
    });

    test("token is NOT flagged as expired", () => {
      const _tokens = {
        ...TOKEN_DATA,
        expires_at: getDayjs().add(1, "hour").toISOString(),
        expires_at_timestamp: getDayjs().add(1, "hour").unix(),
        session_expires_at: getDayjs().add(1, "hour").toISOString(),
        session_expires_at_timestamp: getDayjs().add(1, "hour").unix(),
      };
      tokens.storeTokens(_tokens);
      const expired = tokens.tokenExpired();
      expect(expired).toBe(false);
    });
  });

  describe("sessionExpired", () => {
    test("session is flagged as expired", () => {
      tokens.storeTokens(TOKEN_RESPONSE);
      vi.advanceTimersByTime(3601 * 1000);
      const expired = tokens.sessionExpired();
      expect(expired).toBe(true);
    });
  });

  describe("genTokens", () => {
    test("generates stored tokens with converted date values", () => {
      const result = tokens.genTokens(TOKEN_RESPONSE);

      expect(result).toEqual(TOKEN_DATA);
    });
  });

  describe("setSessionExpiredTimeout", async () => {
    const clearTimeoutSpy = vi.spyOn(window, "clearTimeout");
    const events = await import("lib/events");
    const dispatchCustomEventSpy = vi.spyOn(events, "dispatchCustomEvent");
    beforeEach(() => {
      clearTimeoutSpy.mockClear();
      dispatchCustomEventSpy.mockClear();
    });
    afterEach(() => {
      clearTimeoutSpy.mockClear();
      dispatchCustomEventSpy.mockClear();
    });

    test("should set session expired timeout", () => {
      const sessionExpiresAt = getDayjs().add(1, "hour");

      tokens.setSessionExpiredTimeout();

      expect(dispatchCustomEventSpy).not.toHaveBeenCalled();

      vi.advanceTimersByTime(
        (sessionExpiresAt.unix() - getDayjs().unix()) * 2000,
      );

      expect(dispatchCustomEventSpy).toHaveBeenCalledTimes(1);
      expect(dispatchCustomEventSpy).toHaveBeenCalledWith("session-expired");
    });

    test("should clear existing session expired timeout", () => {
      // First clear any existing timeout from previous tests
      tokens.clearSessionExpiredTimeout();

      // Create a new spy
      const clearTimeoutSpyLocal = vi.spyOn(window, "clearTimeout");
      tokens.setSessionExpiredTimeout();

      expect(clearTimeoutSpyLocal).not.toHaveBeenCalled();
      expect(dispatchCustomEventSpy).not.toHaveBeenCalled();

      tokens.setSessionExpiredTimeout();

      expect(clearTimeoutSpyLocal).toHaveBeenCalledTimes(1);
      expect(dispatchCustomEventSpy).not.toHaveBeenCalled();

      clearTimeoutSpyLocal.mockClear();
    });
  });
});
