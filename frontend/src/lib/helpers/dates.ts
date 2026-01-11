import dayjs, { Dayjs } from "dayjs";

export const DATE_FORMAT = "YYYY-MM-DD";

export function is12HourFormat() {
  const format = new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
  }).resolvedOptions().hourCycle;
  return !!format?.startsWith("h12");
}

export function isDateFormat(str: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(str);
}

// Get a timezone aware dayjs instance for the current time
export function getDayjs() {
  return dayjs().tz();
}

// Get a timezone aware dayjs instance from a Date object
export function getDayjsFromDate(date: Date) {
  return dayjs(date).tz();
}

// Get a timezone aware dayjs instance from a time string
// eg. "2026-01-10T17:20:09.263303+00:00"
export function getDayjsFromDateTimeString(dateString: string) {
  return dayjs(dateString).tz();
}

// Get a timezone aware dayjs instance from a date string
// eg. "2026-01-10"
export function getDayjsFromDateString(dateString: string) {
  return dayjs.tz(dateString);
}

// Get a timezone aware dayjs instance from a unix timestamp
// Supports both seconds and milliseconds
// Milliseconds are converted to seconds
export function getDayjsFromUnixTimestamp(timestamp: number) {
  if (timestamp.toString().length === 13) {
    timestamp = Math.floor(timestamp / 1000);
  }
  return dayjs.unix(timestamp).tz();
}

// Format a dayjs instance to a time string HH:mm:ss or HH:mm
export function getTimeStringFromDayjs(date: Dayjs, seconds = true) {
  return date.format(seconds ? "HH:mm:ss" : "HH:mm");
}

// Format a dayjs instance to a date string YYYY-MM-DD
export function getDateStringFromDayjs(date: Dayjs) {
  return date.format(DATE_FORMAT);
}
