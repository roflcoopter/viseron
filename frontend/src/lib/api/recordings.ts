import { UseQueryOptions, useMutation, useQuery } from "@tanstack/react-query";

import { useToast } from "hooks/UseToast";
import queryClient, {
  useInvalidateQueryOnEvent,
  viseronAPI,
} from "lib/api/client";
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

type DeleteRecordingParams = {
  identifier: string;
  date?: string;
  recording_id?: number;
  failed?: boolean;
};

async function deleteRecording({
  identifier,
  date,
  recording_id,
  failed,
}: DeleteRecordingParams) {
  const url = `/recordings/${identifier}${date ? `/${date}` : ""}${
    recording_id ? `/${recording_id}` : ""
  }`;

  const response = await viseronAPI.delete(
    url,
    failed ? { params: { failed: true } } : undefined,
  );
  return response.data;
}

export const useDeleteRecording = () => {
  const toast = useToast();
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    DeleteRecordingParams
  >({
    mutationFn: deleteRecording,
    onSuccess: async (_data, variables, _context) => {
      toast.success("Recording deleted successfully");
      await queryClient.invalidateQueries({
        queryKey: ["recordings", variables.identifier],
      });
    },
    onError: async (error, _variables, _context) => {
      toast.error(
        error.response && error.response.data.error
          ? `Error deleting recording: ${error.response.data.error}`
          : `An error occurred: ${error.message}`,
      );
    },
  });
};
