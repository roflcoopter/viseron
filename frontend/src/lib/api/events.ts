import {
  UseQueryOptions,
  UseQueryResult,
  useQueries,
  useQuery,
} from "@tanstack/react-query";

import { viseronAPI } from "lib/api/client";
import * as types from "lib/types";

type EventsVariablesWithTime = {
  camera_identifier: string | null;
  time_from: number;
  time_to: number;
  configOptions?: Omit<
    UseQueryOptions<types.CameraEvents, types.APIErrorResponse>,
    "queryKey" | "queryFn"
  >;
};
type EventsVariablesWithDate = {
  camera_identifier: string | null;
  date: string;
  configOptions?: Omit<
    UseQueryOptions<types.CameraEvents, types.APIErrorResponse>,
    "queryKey" | "queryFn"
  >;
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

  return useQuery({
    queryKey,
    queryFn: async () => events(variables),
    ...variables.configOptions,
  });
}

type EventsMultipleVariablesWithTime = {
  camera_identifiers: string[];
  time_from: number;
  time_to: number;
  configOptions?: Omit<
    UseQueryOptions<types.CameraEvents, types.APIErrorResponse>,
    "queryKey" | "queryFn"
  >;
};
type EventsMultipleVariablesWithDate = {
  camera_identifiers: string[];
  date: string;
  configOptions?: Omit<
    UseQueryOptions<types.CameraEvents, types.APIErrorResponse>,
    "queryKey" | "queryFn"
  >;
};
type EventsMultipleVariables =
  | EventsMultipleVariablesWithTime
  | EventsMultipleVariablesWithDate;

export function useEventsMultiple(variables: EventsMultipleVariables) {
  const queryKeys = variables.camera_identifiers.map((camera_identifier) =>
    "time_from" in variables && "time_to" in variables
      ? ["events", camera_identifier, variables.time_from, variables.time_to]
      : ["events", camera_identifier, variables.date],
  );

  const eventsQueries = useQueries({
    queries: queryKeys.map((queryKey) => ({
      queryKey,
      queryFn: async () => {
        const { camera_identifiers, ...newVariables } = variables;
        (newVariables as EventsVariables).camera_identifier =
          queryKey[1] as string;

        return events(newVariables as EventsVariables);
      },
      ...variables.configOptions,
    })),
    combine: (results) => {
      const data = results.flatMap((result) =>
        result.data ? result.data.events : [],
      );
      // Sort latest events first
      data.sort((a, b) => b.created_at_timestamp - a.created_at_timestamp);

      return {
        data,
        isError: results.some((query) => query.isError),
        error: results.find((query) => query.error)?.error,
        isPending: results.some((query) => query.isPending),
        isLoading: results.some((query) => query.isLoading),
      };
    },
  });

  return eventsQueries;
}

type EventsAmountVariables = {
  camera_identifier: string | null;
  configOptions?: Omit<
    UseQueryOptions<types.EventsAmount, types.APIErrorResponse>,
    "queryKey" | "queryFn"
  >;
};

async function eventsAmount({
  camera_identifier,
}: EventsAmountVariables): Promise<types.EventsAmount> {
  const response = await viseronAPI.get<types.EventsAmount>(
    `events/${camera_identifier}/amount`,
  );
  return response.data;
}

export function useEventsAmount(
  variables: EventsAmountVariables,
): UseQueryResult<types.EventsAmount, types.APIErrorResponse> {
  return useQuery({
    queryKey: ["events", variables.camera_identifier, "amount"],
    queryFn: async () => eventsAmount(variables),
    ...variables.configOptions,
  });
}

type EventsAmountMultipleVariables = {
  camera_identifiers: string[];
  configOptions?: Omit<
    UseQueryOptions<types.EventsAmount, types.APIErrorResponse>,
    "queryKey" | "queryFn"
  >;
};

async function eventsAmountMultiple({
  camera_identifiers,
}: EventsAmountMultipleVariables): Promise<types.EventsAmount> {
  const response = await viseronAPI.post<types.EventsAmount>("events/amount", {
    camera_identifiers,
  });
  return response.data;
}

export function useEventsAmountMultiple(
  variables: EventsAmountMultipleVariables,
): UseQueryResult<types.EventsAmount, types.APIErrorResponse> {
  return useQuery({
    queryKey: ["events", "amount"],
    queryFn: async () => eventsAmountMultiple(variables),
    ...variables.configOptions,
  });
}
