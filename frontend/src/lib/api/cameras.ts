import { UseQueryOptions, useQuery } from "@tanstack/react-query";

import { useInvalidateQueryOnEvent, viseronAPI } from "lib/api/client";
import * as types from "lib/types";

type CamerasVariables = {
  configOptions?: Omit<
    UseQueryOptions<types.Cameras, types.APIErrorResponse>,
    "queryKey" | "queryFn"
  >;
};
async function cameras() {
  const response = await viseronAPI.get<types.Cameras>("cameras");
  return response.data;
}

export const useCameras = ({ configOptions }: CamerasVariables) => {
  useInvalidateQueryOnEvent([
    {
      event: "domain/registered/camera",
      queryKey: ["cameras"],
    },
  ]);

  return useQuery({
    queryKey: ["cameras"],
    queryFn: async () => cameras(),
    ...configOptions,
  });
};

type CamerasFailedVariables = {
  configOptions?: Omit<
    UseQueryOptions<types.FailedCameras, types.APIErrorResponse>,
    "queryKey" | "queryFn"
  >;
};
async function camerasFailed() {
  const response = await viseronAPI.get<types.FailedCameras>("cameras/failed");
  return response.data;
}

export const useCamerasFailed = ({ configOptions }: CamerasFailedVariables) => {
  useInvalidateQueryOnEvent([
    {
      event: "domain/setup/domain_failed/camera/*",
      queryKey: ["cameras", "failed"],
    },
    {
      event: "domain/setup/domain_loaded/camera/*",
      queryKey: ["cameras", "failed"],
    },
  ]);

  return useQuery({
    queryKey: ["cameras", "failed"],
    queryFn: async () => camerasFailed(),
    ...configOptions,
  });
};
