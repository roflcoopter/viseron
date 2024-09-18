import { UseQueryOptions, useQuery } from "@tanstack/react-query";

import { useInvalidateQueryOnEvent, viseronAPI } from "lib/api/client";
import * as types from "lib/types";

type RecordingsVariables = {
  camera_identifier: string | null;
  date?: string;
  latest?: boolean;
  daily?: boolean;
  failed?: boolean;
  configOptions?: Omit<
    UseQueryOptions<types.RecordingsCamera, types.APIErrorResponse>,
    "queryKey" | "queryFn"
  >;
};
async function recordings({
  camera_identifier,
  date,
  latest,
  daily,
  failed,
}: RecordingsVariables) {
  const response = await viseronAPI.get<types.RecordingsCamera>(
    `recordings/${camera_identifier}${date ? `/${date}` : ""}`,
    {
      params: {
        ...(latest ? { latest } : null),
        ...(daily ? { daily } : null),
        ...(failed ? { failed } : null),
      },
    },
  );
  return response.data;
}

export const useRecordings = ({
  camera_identifier,
  date,
  latest,
  daily,
  failed,
  configOptions,
}: RecordingsVariables) => {
  useInvalidateQueryOnEvent([
    {
      event: `${camera_identifier}/recorder/start`,
      queryKey: ["recordings", camera_identifier],
    },
    {
      event: `${camera_identifier}/recorder/stop`,
      queryKey: ["recordings", camera_identifier],
    },
  ]);

  if (camera_identifier === null && configOptions?.enabled) {
    throw new Error(
      "camera_identifier can only be null while query is disabled",
    );
  }

  return useQuery({
    queryKey: ["recordings", camera_identifier, date, latest, daily, failed],
    queryFn: async () =>
      recordings({ camera_identifier, date, latest, daily, failed }),
    ...configOptions,
  });
};
