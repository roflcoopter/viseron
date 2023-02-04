import axios from "axios";
import { QueryClient, useMutation } from "react-query";

import { useSnackbar } from "context/SnackbarContext";
import * as types from "lib/types";

export const API_V1_URL = "/api/v1";
export const viseronAPI = axios.create({
  baseURL: API_V1_URL,
  // Match Tornado XSRF protection
  xsrfCookieName: "_xsrf",
  xsrfHeaderName: "X-Xsrftoken",
  headers: {
    "Content-Type": "application/json",
  },
});
export const clientId = (): string => `${location.protocol}//${location.host}/`;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
      staleTime: 30000,
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
  filename?: string;
};

async function deleteRecording({
  identifier,
  date,
  filename,
}: deleteRecordingParams) {
  const url = `${API_V1_URL}/recordings/${identifier}${date ? `/${date}` : ""}${
    filename ? `/${filename}` : ""
  }`;

  const response = await viseronAPI.delete(url);
  return response.data;
}

export const useDeleteRecording = () => {
  const snackbar = useSnackbar();
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    deleteRecordingParams
  >({
    mutationFn: deleteRecording,
    onSuccess: async (_data, variables, _context) => {
      snackbar.showSnackbar("Recording deleted successfully", "success");
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
      snackbar.showSnackbar(
        error.response && error.response.data.error
          ? `Error deleting recording: ${error.response.data.error}`
          : `An error occurred: ${error.message}`,
        "error"
      );
    },
  });
};

export default queryClient;
