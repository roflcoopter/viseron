import { useQueryClient } from "@tanstack/react-query";
import React, { FC, createContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { toastIds, useToast } from "hooks/UseToast";
import { getCameras, subscribeCameras, subscribeRecording } from "lib/commands";
import { sortObj } from "lib/helpers";
import * as types from "lib/types";
import { Connection } from "lib/websockets";

export type ViseronProviderProps = {
  children: React.ReactNode;
};

export type ViseronContextState = {
  connection: Connection | undefined;
  connected: boolean;
  cameras: string[];
};

const contextDefaultValues: ViseronContextState = {
  connection: undefined,
  connected: false,
  cameras: [],
};

export const ViseronContext =
  createContext<ViseronContextState>(contextDefaultValues);

export const ViseronProvider: FC<ViseronProviderProps> = ({
  children,
}: ViseronProviderProps) => {
  const [connection, setConnection] = useState<Connection | undefined>(
    undefined
  );
  const [connected, setConnected] = useState<boolean>(false);
  const [cameras, setCameras] = useState<string[]>([]);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();

  const onConnectRef = React.useRef<() => void>();
  const onDisconnectRef = React.useRef<() => void>();
  const onConnectionErrorRef = React.useRef<() => void>();
  useEffect(() => {
    if (connection) {
      const cameraRegistered = async (camera: types.Camera) => {
        setCameras((prevCameras) => {
          if (prevCameras.includes(camera.identifier)) return prevCameras;
          return [...prevCameras, camera.identifier].sort();
        });
        await queryClient.invalidateQueries({
          predicate: (query) =>
            (query.queryKey[0] as string).startsWith(
              `/recordings/${camera.identifier}`
            ),
        });
      };
      const newRecording = async (
        recordingEvent: types.EventRecorderComplete
      ) => {
        await queryClient.invalidateQueries({
          predicate: (query) =>
            (query.queryKey[0] as string).startsWith(
              `/recordings/${recordingEvent.data.camera.identifier}`
            ),
        });
      };

      onConnectRef.current = async () => {
        const registeredCameras = await getCameras(connection);
        setCameras(Object.keys(sortObj(registeredCameras)).sort());
        await queryClient.invalidateQueries({
          queryKey: ["camera"],
          refetchType: "none",
        });
        setConnected(true);
      };
      onDisconnectRef.current = async () => {
        setConnected(false);
      };
      onConnectionErrorRef.current = async () => {
        console.error("Connection error, redirecting to login");
        navigate("/login");
      };

      connection.addEventListener("connected", onConnectRef.current);
      connection.addEventListener("disconnected", onDisconnectRef.current);
      connection.addEventListener(
        "connection-error",
        onConnectionErrorRef.current
      );

      const connect = async () => {
        subscribeCameras(connection, cameraRegistered); // call without await to not block
        subscribeRecording(connection, newRecording); // call without await to not block
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
            onDisconnectRef.current
          );
        }

        if (onConnectionErrorRef.current) {
          connection.removeEventListener(
            "connection-error",
            onConnectionErrorRef.current
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
    <ViseronContext.Provider value={{ connection, connected, cameras }}>
      {children}
    </ViseronContext.Provider>
  );
};
