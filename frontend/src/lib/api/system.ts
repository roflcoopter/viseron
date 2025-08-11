import { UseQueryOptions, useQuery } from "@tanstack/react-query";

import { viseronAPI } from "lib/api/client";
import * as types from "lib/types";

async function systemDispatchedEvents() {
  const response = await viseronAPI.get(`system/dispatched_events`);
  return response.data;
}

export function useSystemDispatchedEvents(
  configOptions?: Omit<
    UseQueryOptions<types.SystemDispatchedEvents, types.APIErrorResponse>,
    "queryKey" | "queryFn"
  >,
) {
  return useQuery({
    queryKey: ["system", "dispatched_events"],
    queryFn: async () => systemDispatchedEvents(),
    ...configOptions,
  });
}
