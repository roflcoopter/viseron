import { UseQueryOptions, useQuery } from "@tanstack/react-query";

import { viseronAPI } from "lib/api/client";
import * as types from "lib/types";

type EventsVariables = {
  camera_identifier: string | null;
  time_from: number;
  time_to: number;
  configOptions?: UseQueryOptions<types.CameraEvents, types.APIErrorResponse>;
};
async function events({
  camera_identifier,
  time_from,
  time_to,
}: EventsVariables) {
  const response = await viseronAPI.get<types.CameraEvents>(
    `events/${camera_identifier}`,
    {
      params: {
        time_from,
        time_to,
      },
    },
  );
  return response.data;
}

export const useEvents = ({
  camera_identifier,
  time_from,
  time_to,
  configOptions,
}: EventsVariables) =>
  useQuery<types.CameraEvents, types.APIErrorResponse>(
    ["events", camera_identifier, time_from, time_to],
    async () => events({ camera_identifier, time_from, time_to }),
    configOptions,
  );
