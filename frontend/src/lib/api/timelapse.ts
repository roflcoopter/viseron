import {
  UseQueryOptions,
  UseQueryResult,
  useQuery,
} from "@tanstack/react-query";
import { useMemo } from "react";

import { viseronAPI } from "lib/api/client";
import { EventQueryPair, useInvalidateQueryOnEvent } from "lib/api/utils";
import * as types from "lib/types";

// A frame is saved every 5 seconds per camera
const FRAME_EVENT_DEBOUNCE = 10;

const frameCreatedEvent = (camera_identifier: string) =>
  `file_created/${camera_identifier}/timelapse/timelapse`;

type TimelapseSummaryVariables = {
  configOptions?: Omit<
    UseQueryOptions<types.TimelapseSummaryResponse, types.APIErrorResponse>,
    "queryKey" | "queryFn"
  >;
};

async function timelapseSummary(): Promise<types.TimelapseSummaryResponse> {
  const response =
    await viseronAPI.get<types.TimelapseSummaryResponse>("timelapse");
  return response.data;
}

export function useTimelapseSummary(
  variables: TimelapseSummaryVariables = {},
): UseQueryResult<types.TimelapseSummaryResponse, types.APIErrorResponse> {
  const queryKey = ["timelapse", "summary"];
  const query = useQuery({
    queryKey,
    queryFn: timelapseSummary,
    ...variables.configOptions,
  });

  const cameraIdentifiers = Object.keys(query.data?.cameras ?? {});
  const eventQueryPairs: EventQueryPair[] = cameraIdentifiers.map(
    (camera_identifier) => ({
      event: frameCreatedEvent(camera_identifier),
      queryKey,
    }),
  );
  useInvalidateQueryOnEvent(eventQueryPairs, FRAME_EVENT_DEBOUNCE);

  return query;
}

type TimelapseFramesVariables = {
  camera_identifier: string;
  start: number;
  // null means up to now, which also refetches when new frames are saved
  end: number | null;
  max_frames?: number;
  configOptions?: Omit<
    UseQueryOptions<types.TimelapseFramesResponse, types.APIErrorResponse>,
    "queryKey" | "queryFn"
  >;
};

async function timelapseFrames({
  camera_identifier,
  start,
  end,
  max_frames,
}: TimelapseFramesVariables): Promise<types.TimelapseFramesResponse> {
  const response = await viseronAPI.get<types.TimelapseFramesResponse>(
    `timelapse/${camera_identifier}`,
    {
      params: {
        start,
        end: end ?? Date.now() / 1000,
        max_frames,
      },
    },
  );
  return response.data;
}

export function useTimelapseFrames(
  variables: TimelapseFramesVariables,
): UseQueryResult<types.TimelapseFramesResponse, types.APIErrorResponse> {
  const { camera_identifier, start, end, max_frames } = variables;
  const queryKey = useMemo(
    () => [
      "timelapse",
      "frames",
      camera_identifier,
      start,
      end ?? "now",
      max_frames,
    ],
    [camera_identifier, start, end, max_frames],
  );

  useInvalidateQueryOnEvent(
    end === null
      ? [{ event: frameCreatedEvent(camera_identifier), queryKey }]
      : [],
    FRAME_EVENT_DEBOUNCE,
  );

  return useQuery({
    queryKey,
    queryFn: async () => timelapseFrames(variables),
    ...variables.configOptions,
  });
}

type TimelapseDatesOfInterestVariables = {
  camera_identifier: string;
  configOptions?: Omit<
    UseQueryOptions<types.TimelapseDatesOfInterest, types.APIErrorResponse>,
    "queryKey" | "queryFn"
  >;
};

async function timelapseDatesOfInterest({
  camera_identifier,
}: TimelapseDatesOfInterestVariables): Promise<types.TimelapseDatesOfInterest> {
  const response = await viseronAPI.get<types.TimelapseDatesOfInterest>(
    `timelapse/${camera_identifier}/dates_of_interest`,
  );
  return response.data;
}

// Not invalidated on new frames, the set of days only changes at midnight or
// when frames are pruned, and counting every frame is costly
export function useTimelapseDatesOfInterest(
  variables: TimelapseDatesOfInterestVariables,
): UseQueryResult<types.TimelapseDatesOfInterest, types.APIErrorResponse> {
  return useQuery({
    queryKey: ["timelapse", "dates_of_interest", variables.camera_identifier],
    queryFn: async () => timelapseDatesOfInterest(variables),
    ...variables.configOptions,
  });
}
