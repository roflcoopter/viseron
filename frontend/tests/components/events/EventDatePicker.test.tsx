import { describe, expect } from "vitest";

import { getHighlightedDays } from "components/events/EventDatePicker";

describe("getHighlightedDays", () => {
  it("should return an empty object for an empty input", () => {
    const input = {};
    const result = getHighlightedDays(input);
    expect(result).toEqual({});
  });

  it("should count recordings correctly for a non-empty input", () => {
    const input = {
      "2023-03-03": {
        6: {
          /* Recording details */
        },
        5: {
          /* Recording details */
        },
      },
      "2023-03-02": {
        4: {
          /* Recording details */
        },
        3: {
          /* Recording details */
        },
      },
      "2023-03-01": {
        2: {
          /* Recording details */
        },
        1: {
          /* Recording details */
        },
      },
    } as any;
    const result = getHighlightedDays(input);
    expect(result).toEqual({
      "2023-03-03": 2,
      "2023-03-02": 2,
      "2023-03-01": 2,
    });
  });
});
