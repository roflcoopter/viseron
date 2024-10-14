import { describe, expect } from "vitest";

import { getHighlightedDays } from "components/events/EventDatePickerDialog";
import * as types from "lib/types";

describe("getHighlightedDays", () => {
  it("should return an empty object for an empty input", () => {
    const input = {};
    const result = getHighlightedDays(input);
    expect(result).toEqual({});
  });

  it("should count recordings correctly for a non-empty input", () => {
    const input: types.EventsAmount["events_amount"] = {
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
    } as any;
    const result = getHighlightedDays(input);
    expect(result).toEqual({
      "2023-03-03": 10,
      "2023-03-02": 2,
      "2023-03-01": 1,
    });
  });
});
