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
  utc_offset_minutes: number;
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
    params.utc_offset_minutes = variables.utc_offset_minutes;
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
      : [
          "events",
          variables.camera_identifier,
          variables.date,
          variables.utc_offset_minutes,
        ];

  return useQuery<types.CameraEvents, types.APIErrorResponse>(
    queryKey,
    async () => events(variables),
    variables.configOptions,
  );
}

type EventsAmountVariables = {
  camera_identifier: string | null;
  utc_offset_minutes: number;
  configOptions?: UseQueryOptions<types.EventsAmount, types.APIErrorResponse>;
};

async function eventsAmount({
  camera_identifier,
  utc_offset_minutes,
}: EventsAmountVariables): Promise<types.EventsAmount> {
  const response = await viseronAPI.get<types.EventsAmount>(
    `events/${camera_identifier}/amount`,
    {
      params: {
        utc_offset_minutes,
      },
    },
  );
  return response.data;
}

export function useEventsAmount(
  variables: EventsAmountVariables,
): UseQueryResult<types.EventsAmount, types.APIErrorResponse> {
  return useQuery<types.EventsAmount, types.APIErrorResponse>(
    ["events", variables.camera_identifier, "amount"],
    async () => eventsAmount(variables),
    variables.configOptions,
  );
}
