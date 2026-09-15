import dayjs, { Dayjs } from "dayjs";
import timezone from "dayjs/plugin/timezone.js";
import utc from "dayjs/plugin/utc.js";

import { getDayjs as getRealDayjs } from "lib/helpers/dates";

dayjs.extend(utc);
dayjs.extend(timezone);

// handlers.ts is also bundled into the browser for the mocked demo build, where the
// Node `process` global does not exist. Guard the lookup so importing this module
// cannot throw there.
function fixedTime(): string | undefined {
  return typeof process === "undefined"
    ? undefined
    : process.env?.PLAYWRIGHT_FIXED_TIME;
}

// @msw/playwright intercepts via context.route(), so handlers run in Node and are not
// affected by page.clock. The docs screenshot run pins them here instead. UTC matches
// the browser's timezoneId so day-boundary keys agree on both sides.
export function getDayjs(): Dayjs {
  const fixed = fixedTime();
  return fixed ? dayjs(fixed).tz("UTC") : getRealDayjs();
}
