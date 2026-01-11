export function is12HourFormat() {
  const format = new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
  }).resolvedOptions().hourCycle;
  return !!format?.startsWith("h12");
}

export function isDateFormat(str: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(str);
}
