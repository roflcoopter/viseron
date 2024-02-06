import { UseQueryOptions, useQuery } from "@tanstack/react-query";

import { viseronAPI } from "lib/api/client";
import * as types from "lib/types";

type HlsAvailableTimespansVariables = {
  camera_identifier: string | null;
  time_from: number;
  time_to: number;
  configOptions?: UseQueryOptions<
    types.HlsAvailableTimespans,
    types.APIErrorResponse
  >;
};
async function availableTimespans({
  camera_identifier,
  time_from,
  time_to,
}: HlsAvailableTimespansVariables) {
  const response = await viseronAPI.get<types.HlsAvailableTimespans>(
    `hls/${camera_identifier}/available_timespans`,
    {
      params: {
        time_from,
        time_to,
      },
    },
  );
  return response.data;
}

export const useHlsAvailableTimespans = ({
  camera_identifier,
  time_from,
  time_to,
  configOptions,
}: HlsAvailableTimespansVariables) =>
  useQuery<types.HlsAvailableTimespans, types.APIErrorResponse>(
    ["hls", camera_identifier, "available_timespans", time_from, time_to],
    async () => availableTimespans({ camera_identifier, time_from, time_to }),
    configOptions,
  );
