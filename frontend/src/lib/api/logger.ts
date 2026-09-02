import { UseQueryOptions, useQuery } from "@tanstack/react-query";

import { viseronAPI } from "lib/api/client";
import * as types from "lib/types";

export type LogEntry = {
  id: string;
  timestamp?: string;
  timestamp_unix_ms?: number;
  level?: "critical" | "error" | "warning" | "info" | "debug";
  name?: string;
  message?: string;
  raw: string;
  unparsed?: boolean;
};

export type LogsResponse = {
  logs: LogEntry[];
  total_lines_returned: number;
  requested_lines: number;
  file_exists: boolean;
  file_size: number;
  filters: {
    search: string | null;
    level: string | null;
  };
};

export type LoggerConfigResponse = {
  default_level: string;
  logs: Record<string, string>;
  cameras: Record<string, string>;
};

async function getLogs(
  lines?: number,
  search?: string | null,
  level?: string | null,
) {
  const params = new URLSearchParams();
  if (lines) params.append("lines", lines.toString());
  if (search) params.append("search", search);
  if (level) params.append("level", level);

  const response = await viseronAPI.get(
    `logger/logs${params.toString() ? `?${params.toString()}` : ""}`,
  );
  return response.data;
}

export function useLogs(
  lines?: number,
  search?: string | null,
  level?: string | null,
  configOptions?: Omit<
    UseQueryOptions<LogsResponse, types.APIErrorResponse>,
    "queryKey" | "queryFn"
  >,
) {
  return useQuery({
    queryKey: ["logger", "logs", lines, search, level],
    queryFn: async () => getLogs(lines, search, level),
    ...configOptions,
  });
}

async function getLoggerConfig() {
  const response = await viseronAPI.get("logger/config");
  return response.data;
}

export function useLoggerConfig(
  configOptions?: Omit<
    UseQueryOptions<LoggerConfigResponse, types.APIErrorResponse>,
    "queryKey" | "queryFn"
  >,
) {
  return useQuery({
    queryKey: ["logger", "config"],
    queryFn: async () => getLoggerConfig(),
    ...configOptions,
  });
}
