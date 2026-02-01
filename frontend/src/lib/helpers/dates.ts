import dayjs, { Dayjs } from "dayjs";
import timezone from "dayjs/plugin/timezone";
import utc from "dayjs/plugin/utc";

dayjs.extend(utc);
dayjs.extend(timezone);

export const DATE_FORMAT = "YYYY-MM-DD";

let defaultTimezone: string = Intl.DateTimeFormat().resolvedOptions().timeZone;

export function dayjsSetDefaultTimezone(tz: string) {
  defaultTimezone = tz;
  dayjs.tz.setDefault(tz);
}

export function getDefaultTimezone() {
  return defaultTimezone;
}

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

// Convert ONVIF DateTime object to timezone aware dayjs instance
export function getDayjsFromOnvifDateTime(
  dateTime: {
    Time?: { Hour?: number; Minute?: number; Second?: number };
    Date?: { Year?: number; Month?: number; Day?: number };
  },
  isUtc = false,
) {
  const { Hour = 0, Minute = 0, Second = 0 } = dateTime.Time || {};
  const { Year = 0, Month = 0, Day = 0 } = dateTime.Date || {};

  const dayjsInstance = isUtc ? dayjs().utc() : dayjs();
  return dayjsInstance
    .year(Year)
    .month(Month - 1)
    .date(Day)
    .hour(Hour)
    .minute(Minute)
    .second(Second);
}
