import { Dayjs } from "dayjs";

import {
  getDayjsFromUnixTimestamp,
  getDisplayDateStringFromDayjs,
  getTimeStringFromDayjs,
} from "lib/helpers/dates";

export const DENSITY_OPTIONS = [600, 1800, 5000];
export const DEFAULT_DENSITY = 1800;
export const FPS_OPTIONS = [1, 2, 5, 10, 15, 24, 30, 60];
export const DEFAULT_FPS = 30;
// Mirrors TIMELAPSE_MAX_RENDER_FRAMES and TIMELAPSE_RENDER_WIDTHS in the webserver
export const MAX_RENDER_FRAMES = 18000;
export const RENDER_WIDTHS = [
  { width: 640, label: "360p" },
  { width: 854, label: "480p" },
  { width: 1280, label: "720p" },
  { width: 1920, label: "1080p" },
  { width: 2560, label: "1440p" },
  { width: 3840, label: "2160p" },
];

export const RANGE_PRESETS = [
  { value: "last_hour", label: "Last hour" },
  { value: "last_24h", label: "Last 24h" },
  { value: "today", label: "Today" },
  { value: "yesterday", label: "Yesterday" },
  { value: "last_7_days", label: "Last 7 days" },
] as const;

export type RangePreset = (typeof RANGE_PRESETS)[number]["value"];
export const DEFAULT_PRESET: RangePreset = "last_24h";

// end is null when the range ends now
export type TimelapseRange = { start: number; end: number | null };

export type TimelapseSelection =
  { preset: RangePreset } | ({ preset?: undefined } & TimelapseRange);

const isPreset = (value: string | null): value is RangePreset =>
  RANGE_PRESETS.some((preset) => preset.value === value);

const parseTimestamp = (value: string | null) => {
  if (value === null || value === "") {
    return null;
  }
  const timestamp = Number(value);
  return Number.isFinite(timestamp) ? timestamp : null;
};

export function parseSelection(params: URLSearchParams): TimelapseSelection {
  const preset = params.get("range");
  if (isPreset(preset)) {
    return { preset };
  }
  const start = parseTimestamp(params.get("start"));
  const end = parseTimestamp(params.get("end"));
  if (start !== null && (end === null || end > start)) {
    return { start, end };
  }
  return { preset: DEFAULT_PRESET };
}

export function parseDensity(params: URLSearchParams) {
  const density = Number(params.get("frames"));
  return DENSITY_OPTIONS.includes(density) ? density : DEFAULT_DENSITY;
}

export function selectionParams(
  selection: TimelapseSelection,
  density: number,
): Record<string, string> {
  const params: Record<string, string> = {};
  if (selection.preset) {
    params.range = selection.preset;
  } else {
    params.start = String(selection.start);
    if (selection.end !== null) {
      params.end = String(selection.end);
    }
  }
  if (density !== DEFAULT_DENSITY) {
    params.frames = String(density);
  }
  return params;
}

export function presetRange(preset: RangePreset, now: Dayjs): TimelapseRange {
  switch (preset) {
    case "last_hour":
      return { start: now.subtract(1, "hour").unix(), end: null };
    case "today":
      return { start: now.startOf("day").unix(), end: null };
    case "yesterday":
      return {
        start: now.subtract(1, "day").startOf("day").unix(),
        end: now.startOf("day").unix(),
      };
    case "last_7_days":
      return { start: now.subtract(7, "day").unix(), end: null };
    case "last_24h":
    default:
      return { start: now.subtract(1, "day").unix(), end: null };
  }
}

export function dayRange(day: Dayjs, now: Dayjs): TimelapseRange {
  const start = day.startOf("day");
  const end = start.add(1, "day");
  return { start: start.unix(), end: end.isAfter(now) ? null : end.unix() };
}

export function resolveRange(
  selection: TimelapseSelection,
  now: Dayjs,
): TimelapseRange {
  return selection.preset
    ? presetRange(selection.preset, now)
    : { start: selection.start, end: selection.end };
}

export function formatTimestamp(timestamp: number, seconds = true) {
  const date = getDayjsFromUnixTimestamp(timestamp);
  return `${getDisplayDateStringFromDayjs(date)} ${getTimeStringFromDayjs(date, seconds)}`;
}

// The two largest units, eg "2h 5m", leaving out a trailing zero unit
export function formatDuration(seconds: number) {
  const total = Math.round(seconds);
  const units = [
    { value: Math.floor(total / 86400), suffix: "d" },
    { value: Math.floor((total % 86400) / 3600), suffix: "h" },
    { value: Math.floor((total % 3600) / 60), suffix: "m" },
    { value: total % 60, suffix: "s" },
  ];
  const first = units.findIndex((unit) => unit.value > 0);
  if (first === -1) {
    return "0s";
  }
  return units
    .slice(first, first + 2)
    .filter((unit, index) => index === 0 || unit.value > 0)
    .map((unit) => `${unit.value}${unit.suffix}`)
    .join(" ");
}
