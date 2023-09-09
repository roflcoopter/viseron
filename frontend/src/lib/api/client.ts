import { QueryClient, useMutation } from "@tanstack/react-query";
import axios from "axios";

import { useToast } from "hooks/UseToast";
import * as types from "lib/types";

export const API_V1_URL = "/api/v1";
export const viseronAPI = axios.create({
  baseURL: API_V1_URL,
  // Match Tornado XSRF protection
  xsrfCookieName: "_xsrf",
  xsrfHeaderName: "X-Xsrftoken",
  headers: {
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
  },
});
export const clientId = (): string => `${location.protocol}//${location.host}/`;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60 * 1,
      cacheTime: 1000 * 60 * 5,
      queryFn: async ({ queryKey: [url] }) => {
        if (typeof url === "string") {
          const response = await viseronAPI.get(`${url.toLowerCase()}`);
          return response.data;
        }
        throw new Error("Invalid QueryKey");
      },
    },
  },
});

export type deleteRecordingParams = {
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
}: deleteRecordingParams) {
  const url = `/recordings/${identifier}${date ? `/${date}` : ""}${
    recording_id ? `/${recording_id}` : ""
  }`;

  const response = await viseronAPI.delete(
    url,
    failed ? { params: { failed: true } } : undefined
  );
  return response.data;
}

export const useDeleteRecording = () => {
  const toast = useToast();
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    deleteRecordingParams
  >({
    mutationFn: deleteRecording,
    onSuccess: async (_data, variables, _context) => {
      toast.success("Recording deleted successfully");
      await queryClient.invalidateQueries({
        predicate: (query) =>
          (query.queryKey[0] as string).startsWith(
            `/recordings/${variables.identifier}`
          ),
      });
      await queryClient.invalidateQueries([
        `/recordings/${variables.identifier}`,
      ]);
    },
    onError: async (error, _variables, _context) => {
      toast.error(
        error.response && error.response.data.error
          ? `Error deleting recording: ${error.response.data.error}`
          : `An error occurred: ${error.message}`
      );
    },
  });
};

export default queryClient;
