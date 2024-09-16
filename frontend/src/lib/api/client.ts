import { QueryClient, QueryKey, useMutation } from "@tanstack/react-query";
import axios from "axios";
import dayjs from "dayjs";
import { useContext, useEffect } from "react";

import { ViseronContext } from "context/ViseronContext";
import { useToast } from "hooks/UseToast";
import { subscribeStates } from "lib/commands";
import * as types from "lib/types";
import { SubscriptionUnsubscribe } from "lib/websockets";

export const API_V1_URL = "/api/v1";
export const viseronAPI = axios.create({
  baseURL: API_V1_URL,
  // Match Tornado XSRF protection
  xsrfCookieName: "_xsrf",
  xsrfHeaderName: "X-Xsrftoken",
  headers: {
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "X-Client-UTC-Offset": dayjs().utcOffset().toString(),
  },
});
export const clientId = (): string => `${location.protocol}//${location.host}/`;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60 * 1,
      gcTime: 1000 * 60 * 5,
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
    failed ? { params: { failed: true } } : undefined,
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
            `/recordings/${variables.identifier}`,
          ),
      });
      await queryClient.invalidateQueries({
        queryKey: [`/recordings/${variables.identifier}`],
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

export const useInvalidateQueryOnStateChange = (
  entityId: string,
  queryKey: QueryKey,
) => {
  const { connected, connection, subscriptionRef } = useContext(ViseronContext);
  const staticQueryKey = JSON.stringify(queryKey);
  useEffect(() => {
    if (!subscriptionRef) {
      return () => {};
    }
    if (!subscriptionRef.current[entityId]) {
      subscriptionRef.current[entityId] = {
        count: 0,
        subscribing: false,
        unsubscribe: null,
      };
    }

    const _stateChanged = (_event: types.StateChangedEvent) => {
      queryClient.invalidateQueries({ queryKey });
    };

    subscriptionRef.current[entityId].count++;

    const subscribe = async () => {
      if (
        connection &&
        connected &&
        subscriptionRef.current[entityId].unsubscribe === null &&
        subscriptionRef.current[entityId].count === 1 &&
        !subscriptionRef.current[entityId].subscribing
      ) {
        subscriptionRef.current[entityId].subscribing = true;
        subscriptionRef.current[entityId].unsubscribe = await subscribeStates(
          connection,
          _stateChanged,
          entityId,
          undefined,
          false,
        );
        subscriptionRef.current[entityId].subscribing = false;
      }
    };

    const unsubscribe = async () => {
      subscriptionRef.current[entityId].count--;
      if (
        subscriptionRef.current[entityId].count === 0 &&
        subscriptionRef.current[entityId].unsubscribe
      ) {
        const _unsub = subscriptionRef.current[entityId].unsubscribe;
        subscriptionRef.current[entityId].unsubscribe = null;
        await (_unsub as SubscriptionUnsubscribe)();
      }
    };

    subscribe();

    return () => {
      unsubscribe();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connected, connection, entityId, subscriptionRef, staticQueryKey]);
};

export default queryClient;
