import { UseQueryOptions, useQueries, useQuery } from "@tanstack/react-query";

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

type HlsAvailableTimespansMultipleVariablesWithTime = {
  camera_identifiers: string[];
  time_from: number;
  time_to: number;
  configOptions?: UseQueryOptions<
    types.HlsAvailableTimespans,
    types.APIErrorResponse
  >;
};
type HlsAvailableTimespansMultipleVariablesWithDate = {
  camera_identifiers: string[];
  date: string;
  configOptions?: UseQueryOptions<
    types.HlsAvailableTimespans,
    types.APIErrorResponse
  >;
};
type HlsAvailableTimespansMultipleVariables =
  | HlsAvailableTimespansMultipleVariablesWithTime
  | HlsAvailableTimespansMultipleVariablesWithDate;

export function useHlsAvailableTimespansMultiple(
  variables: HlsAvailableTimespansMultipleVariables,
) {
  const queryKeys = variables.camera_identifiers.map((camera_identifier) =>
    "time_from" in variables && "time_to" in variables
      ? [
          "hls",
          camera_identifier,
          "available_timespans",
          variables.time_from,
          variables.time_to,
        ]
      : ["hls", camera_identifier, "available_timespans", variables.date],
  );

  const availableTimespansQueries = useQueries<
    UseQueryOptions<types.HlsAvailableTimespans, types.APIErrorResponse>[]
  >({
    queries: queryKeys.map((queryKey) => ({
      ...variables.configOptions,
      queryKey,
      queryFn: async () => {
        const { camera_identifiers, ...newVariables } = variables;
        (newVariables as HlsAvailableTimespansVariables).camera_identifier =
          queryKey[1] as string;

        return availableTimespans(
          newVariables as HlsAvailableTimespansVariables,
        );
      },
    })),
  });

  const data: types.HlsAvailableTimespans = { timespans: [] };
  data.timespans = availableTimespansQueries.flatMap((result) =>
    result.data ? result.data.timespans : [],
  );

  return {
    data,
    isError: availableTimespansQueries.some((query) => query.isError),
    error: availableTimespansQueries.find((query) => query.error)?.error,
    isLoading: availableTimespansQueries.some((query) => query.isLoading),
    isInitialLoading: availableTimespansQueries.some(
      (query) => query.isInitialLoading,
    ),
  };
}
