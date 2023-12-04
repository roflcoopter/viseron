import { useQueryClient } from "@tanstack/react-query";
import React, {
  FC,
  createContext,
  useContext,
  useEffect,
  useState,
} from "react";
import { useNavigate } from "react-router-dom";

import { AuthContext } from "context/AuthContext";
import { toastIds, useToast } from "hooks/UseToast";
import {
  subscribeCameras,
  subscribeRecordingStart,
  subscribeRecordingStop,
} from "lib/commands";
import * as types from "lib/types";
import { Connection } from "lib/websockets";

export type ViseronProviderProps = {
  children: React.ReactNode;
};

export type ViseronContextState = {
  connection: Connection | undefined;
  connected: boolean;
};

const contextDefaultValues: ViseronContextState = {
  connection: undefined,
  connected: false,
};

export const ViseronContext =
  createContext<ViseronContextState>(contextDefaultValues);

export const ViseronProvider: FC<ViseronProviderProps> = ({
  children,
}: ViseronProviderProps) => {
  const { auth } = useContext(AuthContext);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();

  const [connection, setConnection] = useState<Connection | undefined>(
    undefined,
  );
  const [connected, setConnected] = useState<boolean>(false);
  const onConnectRef = React.useRef<() => void>();
  const onDisconnectRef = React.useRef<() => void>();
  const onConnectionErrorRef = React.useRef<() => void>();

  useEffect(() => {
    if (connection) {
      const cameraRegistered = async (camera: types.Camera) => {
        await queryClient.invalidateQueries({
          predicate: (query) =>
            (query.queryKey[0] as string).startsWith(
              `/recordings/${camera.identifier}`,
            ),
        });
      };
      const recorderEvent = async (
        event:
          | types.EventRecorderStart
          | types.EventRecorderStop
          | types.EventRecorderComplete,
      ) => {
        await queryClient.invalidateQueries({
          predicate: (query) =>
            (query.queryKey[0] as string).startsWith(
              `/recordings/${event.data.camera.identifier}`,
            ),
        });
      };

      onConnectRef.current = async () => {
        await queryClient.invalidateQueries({
          queryKey: ["camera"],
          refetchType: "none",
        });
        await queryClient.invalidateQueries(["cameras"]);
        setConnected(true);
      };
      onDisconnectRef.current = async () => {
        setConnected(false);
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
        subscribeCameras(connection, cameraRegistered); // call without await to not block
        subscribeRecordingStart(connection, recorderEvent); // call without await to not block
        subscribeRecordingStop(connection, recorderEvent); // call without await to not block
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
        setConnection(undefined);
        toast.dismiss(toastIds.websocketConnecting);
        toast.dismiss(toastIds.websocketConnectionLost);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connection, queryClient]);

  useEffect(() => {
    setConnection(new Connection(toast));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <ViseronContext.Provider value={{ connection, connected }}>
      {children}
    </ViseronContext.Provider>
  );
};
