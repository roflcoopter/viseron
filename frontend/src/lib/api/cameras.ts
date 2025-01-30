import { UseQueryOptions, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

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

type CamerasAllVariables = {
  configOptions?: Omit<
    UseQueryOptions<
      CamerasVariables | CamerasFailedVariables,
      types.APIErrorResponse
    >,
    "queryKey" | "queryFn"
  >;
} | void;

export const useCamerasAll = (variables: CamerasAllVariables = {}) => {
  const configOptions = variables?.configOptions ?? {};
  const camerasQuery = useCameras({ configOptions } as CamerasVariables);
  const failedCamerasQuery = useCamerasFailed({
    configOptions,
  } as CamerasFailedVariables);

  const isLoading = camerasQuery.isPending || failedCamerasQuery.isPending;
  const isError = camerasQuery.isError || failedCamerasQuery.isError;
  const error = camerasQuery.error || failedCamerasQuery.error;

  const combinedData: types.Cameras | types.FailedCameras = useMemo(() => {
    let _combinedData = {};
    if (camerasQuery.data) {
      _combinedData = { ..._combinedData, ...camerasQuery.data };
    }
    if (failedCamerasQuery.data) {
      _combinedData = { ..._combinedData, ...failedCamerasQuery.data };
    }
    return _combinedData;
  }, [camerasQuery.data, failedCamerasQuery.data]);

  return {
    cameras: camerasQuery,
    failedCameras: failedCamerasQuery,
    combinedData,
    isLoading,
    isError,
    error,
  };
};
