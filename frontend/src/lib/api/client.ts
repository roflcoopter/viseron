import axios, { AxiosHeaders } from "axios";
import { QueryClient, useMutation } from "react-query";

import { useSnackbar } from "context/SnackbarContext";
import * as types from "lib/types";

import { authToken } from "./auth";
import { loadTokens } from "./tokens";

export const API_V1_URL = "/api/v1";
export const viseronAPI = axios.create({
  baseURL: API_V1_URL,
  headers: {
    "Content-Type": "application/json",
  },
});
export const clientId = (): string => `${location.protocol}//${location.host}/`;

viseronAPI.interceptors.request.use((config) => {
  const tokens = loadTokens();
  if (tokens) {
    (config.headers as AxiosHeaders).set(
      "Authorization",
      `Bearer ${tokens.access_token}`
    );
  }
  return config;
});

let isFetchingTokens = false;
let tokenPromise: Promise<types.AuthTokenResponse>;

viseronAPI.interceptors.response.use(
  async (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const status = error.response.status;

    if (
      (status === 401 || status === 403) &&
      !originalRequest._retry &&
      !originalRequest.url.includes("/auth")
    ) {
      const storedTokens = loadTokens();
      if (!isFetchingTokens) {
        isFetchingTokens = true;
        tokenPromise = authToken({
          grant_type: "refresh_token",
          refresh_token: storedTokens.refresh_token,
          client_id: clientId(),
        });
      }
      const tokens = await tokenPromise;
      isFetchingTokens = false;

      originalRequest._retry = true;
      originalRequest.headers.authorization = `Bearer ${tokens.access_token}`;

      return axios(originalRequest);
    }

    return Promise.reject(error);
  }
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 30000,
      queryFn: async ({ queryKey: [url] }) => {
        console.log("Querying", url);
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
