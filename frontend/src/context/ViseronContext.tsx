import React, { FC, createContext, useEffect, useState } from "react";

import { sortObj } from "lib/helpers";
import * as types from "lib/types";
import { Connection } from "lib/websockets";

export type ViseronProviderProps = {
  children: React.ReactNode;
};

export type ViseronContextState = {
  cameras: types.Cameras;
};

const contextDefaultValues: ViseronContextState = {
  cameras: {},
};

export const ViseronContext =
  createContext<ViseronContextState>(contextDefaultValues);

export const ViseronProvider: FC<ViseronProviderProps> = ({
  children,
}: ViseronProviderProps) => {
  const [cameras, setCameras] = useState<types.Cameras>({});

  useEffect(() => {
    const ws = new Connection();

    const cameraRegistered = async (camera: types.Camera) => {
      setCameras((prevCameras) => {
        let newCameras = { ...prevCameras };
        newCameras[camera.identifier] = camera;
        newCameras = sortObj(newCameras);
        return newCameras;
      });
    };

    const onConnect = async () => {
      const registeredCameras = await ws!.getCameras();
      setCameras(sortObj(registeredCameras));
    };
    ws.addEventListener("connected", onConnect);

    const connect = async () => {
      ws.subscribeCameras(cameraRegistered); // call without await to not block
      await ws.connect();
    };

    connect();
  }, []);

  return (
    <ViseronContext.Provider value={{ cameras }}>
      {children}
    </ViseronContext.Provider>
  );
};
