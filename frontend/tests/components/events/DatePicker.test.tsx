import { describe, expect } from "vitest";

import { getHighlightedDays } from "components/events/DatePickerDialog";
import * as types from "lib/types";

describe("getHighlightedDays", () => {
  it("should return an empty object for an empty input", () => {
    const events = {};
    const availableTimespans: types.HlsAvailableTimespan[] = [];
    const result = getHighlightedDays(events, availableTimespans);
    expect(result).toEqual({});
  });

  it("should return the correct events and available timespans per day", () => {
    const events: types.EventsAmount["events_amount"] = {
      "2023-03-03": {
        motion: 6,
        object: 4,
      },
      "2023-03-02": {
        motion: 2,
      },
      "2023-03-01": {
        object: 1,
      },
    };
    const availableTimespans: types.HlsAvailableTimespan[] = [
      {
        start: 1677312000,
        end: 1677398400,
        duration: 86400,
      },
      {
        start: 1677398400,
        end: 1677484800,
        duration: 86400,
      },
      {
        start: 1677484800,
        end: 1677571200,
        duration: 86400,
      },
      {
        start: 1677740400,
        end: 1677744000,
        duration: 3600,
      },
    ];
    const result = getHighlightedDays(events, availableTimespans);
    expect(result).toEqual({
      "2023-02-25": {
        events: 0,
        timespanAvailable: true,
      },
      "2023-02-26": {
        events: 0,
        timespanAvailable: true,
      },
      "2023-02-27": {
        events: 0,
        timespanAvailable: true,
      },
      "2023-03-01": {
        events: 1,
        timespanAvailable: false,
      },
      "2023-03-02": {
        events: 2,
        timespanAvailable: true,
      },
      "2023-03-03": {
        events: 10,
        timespanAvailable: false,
      },
    });
  });
});
