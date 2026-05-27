import {
  UseMutationOptions,
  UseQueryOptions,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useMemo } from "react";

import { useToast } from "hooks/UseToast";
import { viseronAPI } from "lib/api/client";
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

export type AddCameraConfigPayload = {
  identifier: string;
  name: string;
  host: string;
  port: number;
  path: string;
  stream_format: "rtsp" | "mjpeg";
  username?: string | null;
  password?: string | null;
  substream_path?: string | null;
  substream_port?: number;
  substream_stream_format?: "rtsp" | "mjpeg";
  idle_timeout: number;
  enable_recorder: boolean;
  enable_nvr: boolean;
  reload: boolean;
};

export type AddCameraConfigResponse = {
  message: string;
  reloaded: boolean;
  restart_required?: boolean;
};

async function addCameraConfig(payload: AddCameraConfigPayload) {
  const response = await viseronAPI.post<AddCameraConfigResponse>(
    "cameras",
    payload,
  );
  return response.data;
}

export const useAddCameraConfig = (
  mutationOptions?: Omit<
    UseMutationOptions<
      AddCameraConfigResponse,
      types.APIErrorResponse,
      AddCameraConfigPayload
    >,
    "mutationFn"
  >,
) => {
  const queryClient = useQueryClient();
  const toast = useToast();

  return useMutation({
    ...mutationOptions,
    mutationFn: addCameraConfig,
    onSuccess: async (data, variables, onMutateResult, context) => {
      toast.success(data.message);
      await queryClient.invalidateQueries({ queryKey: ["cameras"] });
      await queryClient.invalidateQueries({ queryKey: ["cameras", "failed"] });
      await mutationOptions?.onSuccess?.(
        data,
        variables,
        onMutateResult,
        context,
      );
    },
    onError: (error, variables, onMutateResult, context) => {
      toast.error(
        error.response && error.response.data.error
          ? `Error adding camera: ${error.response.data.error}`
          : `An error occurred: ${error.message}`,
      );
      mutationOptions?.onError?.(error, variables, onMutateResult, context);
    },
  });
};

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
