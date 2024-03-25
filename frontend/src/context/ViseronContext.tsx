import { useQueryClient } from "@tanstack/react-query";
import React, { FC, createContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuthContext } from "context/AuthContext";
import { toastIds, useToast } from "hooks/UseToast";
import { Connection } from "lib/websockets";

export type ViseronProviderProps = {
  children: React.ReactNode;
};

export type ViseronContextState = {
  connection: Connection | undefined;
  connected: boolean;
  safeMode: boolean;
};

const contextDefaultValues: ViseronContextState = {
  connection: undefined,
  connected: false,
  safeMode: false,
};

export const ViseronContext =
  createContext<ViseronContextState>(contextDefaultValues);

export const ViseronProvider: FC<ViseronProviderProps> = ({
  children,
}: ViseronProviderProps) => {
  const { auth } = useAuthContext();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();

  const [contextValue, setContextValue] =
    useState<ViseronContextState>(contextDefaultValues);
  const { connection } = contextValue;
  const onConnectRef = React.useRef<() => void>();
  const onDisconnectRef = React.useRef<() => void>();
  const onConnectionErrorRef = React.useRef<() => void>();

  useEffect(() => {
    if (connection) {
      onConnectRef.current = async () => {
        queryClient.invalidateQueries({
          predicate(query) {
            return (
              query.queryKey[0] !== "auth" && query.queryKey[1] !== "enabled"
            );
          },
        });
        setContextValue((prevContextValue) => ({
          ...prevContextValue,
          connected: true,
          safeMode: !!connection.system_information?.safe_mode,
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
};
