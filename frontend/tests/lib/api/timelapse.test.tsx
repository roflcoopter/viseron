import { waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { API_BASE_URL } from "tests/mocks/handlers";
import { server } from "tests/mocks/server";
import { renderHookWithContext } from "tests/utils/renderWithContext";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useTimelapseFrames, useTimelapseSummary } from "lib/api/timelapse";
import { useInvalidateQueryOnEvent } from "lib/api/utils";

vi.mock("lib/api/utils", () => ({ useInvalidateQueryOnEvent: vi.fn() }));

const NOW = 1_800_000_000;

const lastEventQueryPairs = () =>
  vi.mocked(useInvalidateQueryOnEvent).mock.lastCall?.[0];

describe("useTimelapseFrames", () => {
  let requestParams: URLSearchParams;

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(NOW * 1000);
    vi.mocked(useInvalidateQueryOnEvent).mockClear();
    server.use(
      http.get(`${API_BASE_URL}/timelapse/camera1`, ({ request }) => {
        requestParams = new URL(request.url).searchParams;
        return HttpResponse.json({
          camera_identifier: "camera1",
          start: Number(requestParams.get("start")),
          end: Number(requestParams.get("end")),
          step: null,
          total: 0,
          frames: [],
          stream: null,
        });
      }),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it.each([
    {
      name: "fixed range",
      end: 2000,
      expectedEnd: "2000",
      expectedEvents: [],
    },
    {
      name: "range up to now",
      end: null,
      expectedEnd: String(NOW),
      expectedEvents: ["file_created/camera1/timelapse/timelapse"],
    },
  ])(
    "requests a $name and only follows new frames when it ends now",
    async ({ end, expectedEnd, expectedEvents }) => {
      const { result } = renderHookWithContext(() =>
        useTimelapseFrames({
          camera_identifier: "camera1",
          start: 1000,
          end,
          max_frames: 600,
        }),
      );

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(Object.fromEntries(requestParams)).toEqual({
        start: "1000",
        end: expectedEnd,
        max_frames: "600",
      });
      expect(lastEventQueryPairs()?.map(({ event }) => event)).toEqual(
        expectedEvents,
      );
    },
  );
});

describe("useTimelapseSummary", () => {
  it("follows new frames of every camera in the summary", async () => {
    server.use(
      http.get(`${API_BASE_URL}/timelapse`, () =>
        HttpResponse.json({
          cameras: {
            camera1: {
              camera_identifier: "camera1",
              count: 0,
              first_timestamp: null,
              last_timestamp: null,
              latest_frame: null,
            },
            camera2: {
              camera_identifier: "camera2",
              count: 0,
              first_timestamp: null,
              last_timestamp: null,
              latest_frame: null,
            },
          },
        }),
      ),
    );

    const { result } = renderHookWithContext(() => useTimelapseSummary());

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(lastEventQueryPairs()).toEqual([
      {
        event: "file_created/camera1/timelapse/timelapse",
        queryKey: ["timelapse", "summary"],
      },
      {
        event: "file_created/camera2/timelapse/timelapse",
        queryKey: ["timelapse", "summary"],
      },
    ]);
  });
});
