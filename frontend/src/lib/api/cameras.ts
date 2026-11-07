import { UseQueryOptions, useMutation, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { useToast } from "hooks/UseToast";
import queryClient, { viseronAPI } from "lib/api/client";
import { useInvalidateQueryOnEvent } from "lib/api/utils";
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
      event: "domain/setup/failed/camera/*",
      queryKey: ["cameras", "failed"],
    },
    {
      event: "domain/setup/retrying/camera/*",
      queryKey: ["cameras", "failed"],
    },
    {
      event: "domain/setup/loaded/camera/*",
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

type OrphanedCamerasVariables = {
  configOptions?: Omit<
    UseQueryOptions<types.OrphanedCameras, types.APIErrorResponse>,
    "queryKey" | "queryFn"
  >;
} | void;
async function orphanedCameras() {
  const response =
    await viseronAPI.get<types.OrphanedCameras>("cameras/orphaned");
  return response.data;
}

export const useOrphanedCameras = (variables: OrphanedCamerasVariables = {}) =>
  useQuery({
    queryKey: ["cameras", "orphaned"],
    queryFn: async () => orphanedCameras(),
    ...(variables?.configOptions ?? {}),
  });

type DeleteOrphanedCameraParams = {
  camera_identifier: string;
};
async function deleteOrphanedCamera({
  camera_identifier,
}: DeleteOrphanedCameraParams) {
  const response = await viseronAPI.delete<types.OrphanedCamera>(
    `cameras/orphaned/${camera_identifier}`,
  );
  return response.data;
}

export const useDeleteOrphanedCamera = () => {
  const toast = useToast();
  return useMutation<
    types.OrphanedCamera,
    types.APIErrorResponse,
    DeleteOrphanedCameraParams
  >({
    mutationFn: deleteOrphanedCamera,
    onSuccess: async (data, _variables, _context) => {
      toast.success(
        `Deleted ${data.file_count} files for camera ${data.camera_identifier}`,
      );
      await queryClient.invalidateQueries({
        queryKey: ["cameras", "orphaned"],
      });
    },
    onError: async (error, variables, _context) => {
      toast.error(
        error.response && error.response.data.error
          ? `Error deleting ${variables.camera_identifier}: ${error.response.data.error}`
          : `An error occurred: ${error.message}`,
      );
    },
  });
};

async function camerasNotifications(body: types.NotificationsPauseVariables) {
  const response = await viseronAPI.post<types.APISuccessResponse>(
    "/cameras/notifications",
    body,
  );
  return response.data;
}

export const useCamerasNotifications = () => {
  const toast = useToast();
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    types.NotificationsPauseVariables
  >({
    mutationFn: camerasNotifications,
    onSuccess: async (_data, variables, _context) => {
      toast.success(
        `Notifications ${variables.action === "pause" ? "paused" : "resumed"} for all cameras`,
      );
    },
    onError: async (error, variables, _context) => {
      toast.error(
        error.response && error.response.data.error
          ? `Error ${variables.action === "pause" ? "pausing" : "resuming"} notifications: ${error.response.data.error}`
          : `An error occurred: ${error.message}`,
      );
    },
  });
};
