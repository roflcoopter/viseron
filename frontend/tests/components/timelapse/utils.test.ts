import { afterAll, beforeAll, describe, expect, test } from "vitest";

import {
  dayRange,
  formatDuration,
  parseDensity,
  parseSelection,
  presetRange,
  selectionParams,
} from "components/timelapse/utils";
import {
  dayjsSetDefaultTimezone,
  getDayjsFromDateTimeString,
  getDefaultTimezone,
} from "lib/helpers/dates";

const unix = (dateTime: string) => Date.parse(dateTime) / 1000;

describe("timelapse range helpers", () => {
  const timezone = getDefaultTimezone();
  // Day boundaries depend on the timezone
  beforeAll(() => dayjsSetDefaultTimezone("UTC"));
  afterAll(() => dayjsSetDefaultTimezone(timezone));
  const now = () => getDayjsFromDateTimeString("2026-05-10T15:30:00Z");

  test.each([
    { search: "", expected: { preset: "last_24h" } },
    { search: "range=today", expected: { preset: "today" } },
    { search: "start=100", expected: { start: 100, end: null } },
    { search: "start=100&end=200", expected: { start: 100, end: 200 } },
    // An end before the start is not a valid range
    { search: "start=200&end=100", expected: { preset: "last_24h" } },
    { search: "range=invalid", expected: { preset: "last_24h" } },
  ])("parses '$search'", ({ search, expected }) => {
    expect(parseSelection(new URLSearchParams(search))).toEqual(expected);
  });

  test.each([
    { search: "frames=600", expected: 600 },
    { search: "frames=123", expected: 1800 },
    { search: "", expected: 1800 },
  ])("parses density '$search'", ({ search, expected }) => {
    expect(parseDensity(new URLSearchParams(search))).toBe(expected);
  });

  test.each([
    {
      selection: { preset: "today" as const },
      density: 1800,
      expected: { range: "today" },
    },
    {
      selection: { start: 100, end: null },
      density: 600,
      expected: { start: "100", frames: "600" },
    },
    {
      selection: { start: 100, end: 200 },
      density: 1800,
      expected: { start: "100", end: "200" },
    },
  ])("writes $expected", ({ selection, density, expected }) => {
    expect(selectionParams(selection, density)).toEqual(expected);
  });

  test.each([
    {
      preset: "last_hour" as const,
      expected: { start: unix("2026-05-10T14:30:00Z"), end: null },
    },
    {
      preset: "today" as const,
      expected: { start: unix("2026-05-10T00:00:00Z"), end: null },
    },
    {
      preset: "yesterday" as const,
      expected: {
        start: unix("2026-05-09T00:00:00Z"),
        end: unix("2026-05-10T00:00:00Z"),
      },
    },
  ])("resolves $preset", ({ preset, expected }) => {
    expect(presetRange(preset, now())).toEqual(expected);
  });

  test.each([
    {
      name: "a past day",
      day: "2026-05-08T12:00:00Z",
      expected: {
        start: unix("2026-05-08T00:00:00Z"),
        end: unix("2026-05-09T00:00:00Z"),
      },
    },
    {
      name: "today up to now",
      day: "2026-05-10T15:30:00Z",
      expected: { start: unix("2026-05-10T00:00:00Z"), end: null },
    },
  ])("day range of $name", ({ day, expected }) => {
    expect(dayRange(getDayjsFromDateTimeString(day), now())).toEqual(expected);
  });

  test.each([
    { seconds: 0, expected: "0s" },
    { seconds: 10, expected: "10s" },
    { seconds: 60, expected: "1m" },
    { seconds: 90, expected: "1m 30s" },
    { seconds: 3660, expected: "1h 1m" },
    { seconds: 7 * 86400, expected: "7d" },
    // Only the two largest units are shown
    { seconds: 86400 + 3600 + 61, expected: "1d 1h" },
  ])("formats $seconds seconds as $expected", ({ seconds, expected }) => {
    expect(formatDuration(seconds)).toBe(expected);
  });
});
