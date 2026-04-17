import { QueryKey, useQueryClient } from "@tanstack/react-query";
import React, { createContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuthContext } from "context/AuthContext";
import { toastIds, useToast } from "hooks/UseToast";
import { getSetupStatus, subscribeEvent } from "lib/commands";
import * as types from "lib/types";
import { Connection, SubscriptionUnsubscribe } from "lib/websockets";

export type ViseronProviderProps = {
  children: React.ReactNode;
};

type SubscriptionManager = {
  count: number;
  unsubscribe: SubscriptionUnsubscribe | null;
  subscribing: boolean;
  queryKeys: QueryKey[];
};

export type ViseronContextState = {
  connection: Connection | undefined;
  connected: boolean;
  safeMode: boolean;
  version: string | undefined;
  gitCommit: string | undefined;
  setupStatus: types.SetupStatusResponse;
  subscriptionRef:
    | React.MutableRefObject<Record<string, SubscriptionManager>>
    | undefined;
};

const contextDefaultValues: ViseronContextState = {
  connection: undefined,
  connected: false,
  safeMode: false,
  version: undefined,
  gitCommit: undefined,
  setupStatus: { components: [] },
  subscriptionRef: undefined,
};

export const ViseronContext =
  createContext<ViseronContextState>(contextDefaultValues);

export function ViseronProvider({ children }: ViseronProviderProps) {
  const { auth } = useAuthContext();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();

  const subscriptionRef = React.useRef<Record<string, SubscriptionManager>>({});
  const [contextValue, setContextValue] = useState<ViseronContextState>({
    ...contextDefaultValues,
    subscriptionRef,
  });
  const { connection } = contextValue;
  const onConnectRef = React.useRef<() => void>(undefined);
  const onDisconnectRef = React.useRef<() => void>(undefined);
  const onConnectionErrorRef = React.useRef<() => void>(undefined);
  const initialConnectionEstablishedRef = React.useRef(false);
  const statusSubscriptionsRef = React.useRef<SubscriptionUnsubscribe[]>([]);

  useEffect(() => {
    if (connection) {
      onConnectRef.current = async () => {
        // Invalidate all queries ONLY when connection is re-established, not on initial connect
        if (initialConnectionEstablishedRef.current) {
          queryClient.invalidateQueries();
        } else {
          initialConnectionEstablishedRef.current = true;
        }
        setContextValue((prevContextValue) => ({
          ...prevContextValue,
          connected: true,
          safeMode: !!connection.system_information?.safe_mode,
          version: connection.system_information?.version,
          gitCommit: connection.system_information?.git_commit,
        }));

        // Subscribe to component and domain setup status changes
        // and refetch full status when they change.
        const refetchStatus = async () => {
          const result = await getSetupStatus(connection);
          setContextValue((prev) => ({
            ...prev,
            setupStatus: result,
          }));
        };
        if (statusSubscriptionsRef.current.length === 0) {
          const componentSub = await subscribeEvent<types.Event>(
            connection,
            "component/setup/*/*",
            refetchStatus,
          );
          const domainSub = await subscribeEvent<types.Event>(
            connection,
            "domain/setup/*/*/*",
            refetchStatus,
          );
          statusSubscriptionsRef.current = [componentSub, domainSub];
        }

        // Fetch initial setup status
        const result = await getSetupStatus(connection);
        setContextValue((prev) => ({
          ...prev,
          setupStatus: result,
        }));
      };
      onDisconnectRef.current = async () => {
        setContextValue((prevContextValue) => ({
          ...prevContextValue,
          connected: false,
        }));
      };
      onConnectionErrorRef.current = async () => {
        if (auth.enabled) {
          const url = auth.onboarding_complete ? "/login" : "/onboarding";
          console.error(`Connection error, redirecting to ${url}`);
          navigate(url);
        }
      };

      connection.addEventListener("connected", onConnectRef.current);
      connection.addEventListener("disconnected", onDisconnectRef.current);
      connection.addEventListener(
        "connection-error",
        onConnectionErrorRef.current,
      );

      const connect = async () => {
        await connection.connect();
      };
      connect();
    }
    return () => {
      if (connection) {
        if (onConnectRef.current) {
          connection.removeEventListener("connected", onConnectRef.current);
        }
        if (onDisconnectRef.current) {
          connection.removeEventListener(
            "disconnected",
            onDisconnectRef.current,
          );
        }

        if (onConnectionErrorRef.current) {
          connection.removeEventListener(
            "connection-error",
            onConnectionErrorRef.current,
          );
        }
        connection.disconnect();
        for (const unsub of statusSubscriptionsRef.current) {
          unsub();
        }
        statusSubscriptionsRef.current = [];
        setContextValue((prevContextValue) => ({
          ...prevContextValue,
          connection: undefined,
        }));
        toast.dismiss(toastIds.websocketConnecting);
        toast.dismiss(toastIds.websocketConnectionLost);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connection, queryClient]);

  useEffect(() => {
    setContextValue((prevContextValue) => ({
      ...prevContextValue,
      connection: new Connection(toast),
    }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <ViseronContext.Provider value={contextValue}>
      {children}
    </ViseronContext.Provider>
  );
}
