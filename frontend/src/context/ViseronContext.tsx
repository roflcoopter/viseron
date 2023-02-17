import { useQueryClient } from "@tanstack/react-query";
import React, { FC, createContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

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
  cameras: types.Cameras;
};

const contextDefaultValues: ViseronContextState = {
  connection: undefined,
  connected: false,
  cameras: {},
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
  const [cameras, setCameras] = useState<types.Cameras>({});
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const onConnectRef = React.useRef<() => void>();
  const onDisconnectRef = React.useRef<() => void>();
  const onConnectionErrorRef = React.useRef<() => void>();

  useEffect(() => {
    if (connection) {
      const cameraRegistered = async (camera: types.Camera) => {
        setCameras((prevCameras) => {
          let newCameras = { ...prevCameras };
          newCameras[camera.identifier] = camera;
          newCameras = sortObj(newCameras);
          return newCameras;
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
        setConnected(true);
        const registeredCameras = await getCameras(connection);
        setCameras(sortObj(registeredCameras));
      };
      onDisconnectRef.current = async () => {
        setConnected(false);
      };
      onConnectionErrorRef.current = async () => {
        console.error("Connection error, redirecting to login");
        queryClient.removeQueries();
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
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connection, queryClient]);

  useEffect(() => {
    setConnection(new Connection());
  }, []);

  return (
    <ViseronContext.Provider value={{ connection, connected, cameras }}>
      {children}
    </ViseronContext.Provider>
  );
};
