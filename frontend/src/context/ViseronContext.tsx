import React, { FC, createContext, useEffect, useState } from "react";

import { sortObj } from "lib/helpers";
import * as types from "lib/types";
import { Connection } from "lib/websockets";

export type ViseronProviderProps = {
  children: React.ReactNode;
};

export type ViseronContextState = {
  connection: Connection | undefined;
  cameras: types.Cameras;
};

const contextDefaultValues: ViseronContextState = {
  connection: undefined,
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
  const [cameras, setCameras] = useState<types.Cameras>({});

  useEffect(() => {
    if (connection) {
      const cameraRegistered = async (camera: types.Camera) => {
        setCameras((prevCameras) => {
          let newCameras = { ...prevCameras };
          newCameras[camera.identifier] = camera;
          newCameras = sortObj(newCameras);
          return newCameras;
        });
      };

      const onConnect = async () => {
        const registeredCameras = await connection!.getCameras();
        setCameras(sortObj(registeredCameras));
      };
      connection!.addEventListener("connected", onConnect);

      const connect = async () => {
        connection!.subscribeCameras(cameraRegistered); // call without await to not block
        await connection!.connect();
      };
      connect();
    }
  }, [connection]);

  useEffect(() => {
    setConnection(new Connection());
  }, []);

  return (
    <ViseronContext.Provider value={{ cameras, connection }}>
      {children}
    </ViseronContext.Provider>
  );
};
