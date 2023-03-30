import { UseQueryOptions, useQuery } from "@tanstack/react-query";
import { useContext, useEffect } from "react";

import { ViseronContext } from "context/ViseronContext";
import queryClient, { viseronAPI } from "lib/api/client";
import { subscribeCameras, subscribeEvent } from "lib/commands";
import * as types from "lib/types";

type CamerasVariables = {
  configOptions?: UseQueryOptions<types.Cameras, types.APIErrorResponse>;
};
async function cameras() {
  const response = await viseronAPI.get<types.Cameras>("cameras");
  return response.data;
}

export const useCameras = ({ configOptions }: CamerasVariables) => {
  const { connection } = useContext(ViseronContext);

  useEffect(() => {
    let unsub: () => void;
    if (connection) {
      const invalidate = (_camera: types.Camera) => {
        queryClient.invalidateQueries(["cameras"]);
      };

      const subscribe = async () => {
        unsub = await subscribeCameras(connection, invalidate);
      };
      subscribe();
    }
    return () => {
      if (unsub) {
        unsub();
      }
    };
  }, [connection]);

  return useQuery<types.Cameras, types.APIErrorResponse>(
    ["cameras"],
    async () => cameras(),
    configOptions
  );
};

type CamerasFailedVariables = {
  configOptions?: UseQueryOptions<types.FailedCameras, types.APIErrorResponse>;
};
async function camerasFailed() {
  const response = await viseronAPI.get<types.FailedCameras>("cameras/failed");
  return response.data;
}

export const useCamerasFailed = ({ configOptions }: CamerasFailedVariables) => {
  const { connection } = useContext(ViseronContext);

  useEffect(() => {
    const unsubs: (() => void)[] = [];
    if (connection) {
      const invalidate = (_message: types.Event) => {
        queryClient.invalidateQueries(["cameras", "failed"]);
      };

      const subscribe = async () => {
        unsubs.push(
          await subscribeEvent(
            connection,
            "domain/setup/domain_failed/camera/*",
            invalidate
          )
        );
        unsubs.push(
          await subscribeEvent(
            connection,
            "domain/setup/domain_loaded/camera/*",
            invalidate
          )
        );
      };
      subscribe();
    }
    return () => {
      unsubs.forEach((unsubscribe) => unsubscribe());
    };
  }, [connection]);

  return useQuery<types.FailedCameras, types.APIErrorResponse>(
    ["cameras", "failed"],
    async () => camerasFailed(),
    configOptions
  );
};
