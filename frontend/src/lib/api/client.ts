import { QueryClient, QueryKey } from "@tanstack/react-query";
import axios from "axios";
import dayjs from "dayjs";
import { useContext, useEffect } from "react";

import { ViseronContext } from "context/ViseronContext";
import { subscribeEvent, subscribeStates } from "lib/commands";
import * as types from "lib/types";

// Detect base path from the current URL for subpath support
// If running at /viseron/index.html, basePath will be /viseron
// If running at /index.html, basePath will be empty
function getBasePath(): string {
  const path = window.location.pathname;
  return path.substring(0, path.lastIndexOf("/"));
}

export const BASE_PATH = getBasePath();
export const API_V1_URL = `${BASE_PATH}/api/v1`;
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
export const clientId = (): string =>
  `${location.protocol}//${location.host}${BASE_PATH}/`;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
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

// Helper to check if a queryKey already exists in the array to avoid duplicates
const queryKeyExists = (queryKeys: QueryKey[], queryKey: QueryKey): boolean =>
  queryKeys.some(
    (existingKey) => JSON.stringify(existingKey) === JSON.stringify(queryKey),
  );

type EntityQueryPair = {
  entityId: string;
  queryKey: QueryKey;
};

export const useInvalidateQueryOnStateChange = (
  entityQueryPairs: EntityQueryPair[],
) => {
  const { connected, connection, subscriptionRef } = useContext(ViseronContext);
  const staticEntityQueryPairs = JSON.stringify(entityQueryPairs);

  useEffect(() => {
    if (!subscriptionRef) {
      return () => {};
    }

    entityQueryPairs.forEach(({ entityId, queryKey }) => {
      if (!subscriptionRef.current[entityId]) {
        subscriptionRef.current[entityId] = {
          count: 0,
          subscribing: false,
          unsubscribe: null,
          queryKeys: [],
        };
      }

      if (
        !queryKeyExists(subscriptionRef.current[entityId].queryKeys, queryKey)
      ) {
        subscriptionRef.current[entityId].queryKeys.push(queryKey);
      }

      const queryKeys = subscriptionRef.current[entityId].queryKeys;

      const _stateChanged = (_event: types.StateChangedEvent) => {
        queryKeys.forEach((key) => {
          queryClient.invalidateQueries({ queryKey: key });
        });
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

      subscribe();
    });

    const unsubscribe = async (entityId: string) => {
      subscriptionRef.current[entityId].count--;
      if (
        subscriptionRef.current[entityId].count === 0 &&
        subscriptionRef.current[entityId].unsubscribe
      ) {
        const _unsub = subscriptionRef.current[entityId].unsubscribe;
        subscriptionRef.current[entityId].unsubscribe = null;
        await _unsub();
      }
    };

    return () => {
      entityQueryPairs.forEach(({ entityId }) => {
        unsubscribe(entityId);
      });
    };
    // False positive, staticEntityQueryPairs is derived from entityQueryPairs
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connected, connection, subscriptionRef, staticEntityQueryPairs]);
};

export type EventQueryPair = {
  event: string;
  queryKey: QueryKey;
};

export const useInvalidateQueryOnEvent = (
  eventQueryPairs: EventQueryPair[],
  debounce?: number,
) => {
  const { connected, connection, subscriptionRef } = useContext(ViseronContext);
  const staticEventQueryPairs = JSON.stringify(eventQueryPairs);

  useEffect(() => {
    if (!subscriptionRef) {
      return () => {};
    }

    eventQueryPairs.forEach(({ event, queryKey }) => {
      if (!subscriptionRef.current[event]) {
        subscriptionRef.current[event] = {
          count: 0,
          subscribing: false,
          unsubscribe: null,
          queryKeys: [],
        };
      }

      if (!queryKeyExists(subscriptionRef.current[event].queryKeys, queryKey)) {
        subscriptionRef.current[event].queryKeys.push(queryKey);
      }

      const queryKeys = subscriptionRef.current[event].queryKeys;

      const callback = (_event: types.Event) => {
        queryKeys.forEach((key) => {
          queryClient.invalidateQueries({ queryKey: key });
        });
      };

      subscriptionRef.current[event].count++;

      const subscribe = async () => {
        if (
          connection &&
          connected &&
          subscriptionRef.current[event].unsubscribe === null &&
          subscriptionRef.current[event].count === 1 &&
          !subscriptionRef.current[event].subscribing
        ) {
          subscriptionRef.current[event].subscribing = true;
          subscriptionRef.current[event].unsubscribe = await subscribeEvent(
            connection,
            event,
            callback,
            debounce,
          );
          subscriptionRef.current[event].subscribing = false;
        }
      };

      subscribe();
    });

    const unsubscribe = async (event: string) => {
      subscriptionRef.current[event].count--;
      if (
        subscriptionRef.current[event].count === 0 &&
        subscriptionRef.current[event].unsubscribe
      ) {
        const _unsub = subscriptionRef.current[event].unsubscribe;
        subscriptionRef.current[event].unsubscribe = null;
        await _unsub();
      }
    };

    return () => {
      eventQueryPairs.forEach(({ event }) => {
        unsubscribe(event);
      });
    };
    // False positive, staticEventQueryPairs is derived from eventQueryPairs
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connected, connection, subscriptionRef, staticEventQueryPairs]);
};

export default queryClient;
