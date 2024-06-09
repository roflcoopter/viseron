import { UseQueryOptions, useQuery } from "@tanstack/react-query";

import { viseronAPI } from "lib/api/client";
import * as types from "lib/types";

type HlsAvailableTimespansVariablesWithTime = {
  camera_identifier: string | null;
  time_from: number;
  time_to: number;
  configOptions?: UseQueryOptions<
    types.HlsAvailableTimespans,
    types.APIErrorResponse
  >;
};
type HlsAvailableTimespansVariablesWithDate = {
  camera_identifier: string | null;
  date: string;
  configOptions?: UseQueryOptions<
    types.HlsAvailableTimespans,
    types.APIErrorResponse
  >;
};
type HlsAvailableTimespansVariables =
  | HlsAvailableTimespansVariablesWithTime
  | HlsAvailableTimespansVariablesWithDate;

function availableTimespans(
  variables: HlsAvailableTimespansVariablesWithTime,
): Promise<types.HlsAvailableTimespans>;
function availableTimespans(
  variables: HlsAvailableTimespansVariablesWithDate,
): Promise<types.HlsAvailableTimespans>;
function availableTimespans(
  variables: HlsAvailableTimespansVariables,
): Promise<types.HlsAvailableTimespans>;

async function availableTimespans(variables: HlsAvailableTimespansVariables) {
  const { camera_identifier } = variables;

  const params: Record<string, any> = {};
  if ("time_from" in variables && "time_to" in variables) {
    params.time_from = variables.time_from;
    params.time_to = variables.time_to;
  } else if ("date" in variables) {
    params.date = variables.date;
  }

  const response = await viseronAPI.get<types.HlsAvailableTimespans>(
    `hls/${camera_identifier}/available_timespans`,
    {
      params,
    },
  );
  return response.data;
}

export const useHlsAvailableTimespans = (
  variables: HlsAvailableTimespansVariables,
) => {
  const queryKey =
    "time_from" in variables && "time_to" in variables
      ? [
          "hls",
          variables.camera_identifier,
          "available_timespans",
          variables.time_from,
          variables.time_to,
        ]
      : [
          "hls",
          variables.camera_identifier,
          "available_timespans",
          variables.date,
        ];
  return useQuery<types.HlsAvailableTimespans, types.APIErrorResponse>(
    queryKey,
    async () => availableTimespans(variables),
    variables.configOptions,
  );
};
