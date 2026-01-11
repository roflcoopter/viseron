export function is12HourFormat() {
  const format = new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
  }).resolvedOptions().hourCycle;
  return !!format?.startsWith("h12");
}
