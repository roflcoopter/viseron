import {
  UseQueryOptions,
  UseQueryResult,
  useQuery,
} from "@tanstack/react-query";

import { viseronAPI } from "lib/api/client";
import * as types from "lib/types";

type EventsVariablesWithTime = {
  camera_identifier: string | null;
  time_from: number;
  time_to: number;
  configOptions?: UseQueryOptions<types.CameraEvents, types.APIErrorResponse>;
};
type EventsVariablesWithDate = {
  camera_identifier: string | null;
  date: string;
  configOptions?: UseQueryOptions<types.CameraEvents, types.APIErrorResponse>;
};
type EventsVariables = EventsVariablesWithTime | EventsVariablesWithDate;

function events(
  variables: EventsVariablesWithTime,
): Promise<types.CameraEvents>;
function events(
  variables: EventsVariablesWithDate,
): Promise<types.CameraEvents>;
function events(variables: EventsVariables): Promise<types.CameraEvents>;

async function events(variables: EventsVariables): Promise<types.CameraEvents> {
  const { camera_identifier } = variables;

  const params: Record<string, any> = {};
  if ("time_from" in variables && "time_to" in variables) {
    params.time_from = variables.time_from;
    params.time_to = variables.time_to;
  } else if ("date" in variables) {
    params.date = variables.date;
  }

  const response = await viseronAPI.get<types.CameraEvents>(
    `events/${camera_identifier}`,
    {
      params,
    },
  );
  return response.data;
}

// Overloaded function signatures for 'useEvents'
export function useEvents(
  variables: EventsVariablesWithTime,
): UseQueryResult<types.CameraEvents, types.APIErrorResponse>;
export function useEvents(
  variables: EventsVariablesWithDate,
): UseQueryResult<types.CameraEvents, types.APIErrorResponse>;

export function useEvents(variables: EventsVariables) {
  const queryKey =
    "time_from" in variables && "time_to" in variables
      ? [
          "events",
          variables.camera_identifier,
          variables.time_from,
          variables.time_to,
        ]
      : ["events", variables.camera_identifier, variables.date];

  return useQuery<types.CameraEvents, types.APIErrorResponse>(
    queryKey,
    async () => events(variables),
    variables.configOptions,
  );
}
