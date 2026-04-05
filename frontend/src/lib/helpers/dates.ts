import dayjs, { Dayjs } from "dayjs";
import timezone from "dayjs/plugin/timezone.js";
import utc from "dayjs/plugin/utc.js";

dayjs.extend(utc);
dayjs.extend(timezone);

export const DATE_FORMAT = "YYYY-MM-DD";

export type DateFormatOption = {
  value: string;
  label: string;
};

export const VALID_DATE_FORMATS: DateFormatOption[] = [
  { value: "YYYY-MM-DD", label: "YYYY-MM-DD (e.g. 2026-03-20)" },
  { value: "MM/DD/YYYY", label: "MM/DD/YYYY (e.g. 03/20/2026)" },
  { value: "DD/MM/YYYY", label: "DD/MM/YYYY (e.g. 20/03/2026)" },
  { value: "DD.MM.YYYY", label: "DD.MM.YYYY (e.g. 20.03.2026)" },
  { value: "MM-DD-YYYY", label: "MM-DD-YYYY (e.g. 03-20-2026)" },
  { value: "DD-MM-YYYY", label: "DD-MM-YYYY (e.g. 20-03-2026)" },
];

let defaultTimezone: string = Intl.DateTimeFormat().resolvedOptions().timeZone;
let defaultDisplayDateFormat: string = DATE_FORMAT;
let defaultTimeFormat: "12h" | "24h" | null = null;

export function is12HourFormat() {
  if (defaultTimeFormat !== null) {
    return defaultTimeFormat === "12h";
  }
  const format = new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
  }).resolvedOptions().hourCycle;
  return !!format?.startsWith("h12");
}

export function dayjsSetDefaultTimezone(tz: string) {
  defaultTimezone = tz;
  dayjs.tz.setDefault(tz);
}

export function getDefaultTimezone() {
  return defaultTimezone;
}

export function setDefaultDisplayDateFormat(format: string) {
  defaultDisplayDateFormat = format;
}

export function getDisplayDateFormat() {
  return defaultDisplayDateFormat;
}

export function setDefaultTimeFormat(format: "12h" | "24h" | null) {
  defaultTimeFormat = format;
}

export function getDefaultTimeFormat() {
  return defaultTimeFormat;
}

export function getDisplayTimeFormat(seconds = true) {
  if (is12HourFormat()) {
    return seconds ? "h:mm:ss A" : "h:mm A";
  }
  return seconds ? "HH:mm:ss" : "HH:mm";
}

export function getDisplayDateTimeFormat() {
  return `${getDisplayDateFormat()} ${getDisplayTimeFormat()}`;
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
  if (Math.abs(timestamp) > 9999999999) {
    timestamp = Math.floor(timestamp / 1000);
  }
  return dayjs.unix(Math.round(timestamp)).tz();
}

// Format a dayjs instance to a time string HH:mm:ss or HH:mm
export function getTimeStringFromDayjs(date: Dayjs, seconds = true) {
  if (is12HourFormat()) {
    return date.format(seconds ? "h:mm:ss A" : "h:mm A");
  }
  return date.format(seconds ? "HH:mm:ss" : "HH:mm");
}

// Format a dayjs instance to a date string YYYY-MM-DD
export function getDateStringFromDayjs(date: Dayjs) {
  return date.format(DATE_FORMAT);
}

// Format a dayjs instance to a date string using the user's preferred display format
export function getDisplayDateStringFromDayjs(date: Dayjs) {
  return date.format(defaultDisplayDateFormat);
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
