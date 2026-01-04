import { UseQueryOptions, useMutation, useQuery } from "@tanstack/react-query";

import { useToast } from "hooks/UseToast";
import { useInvalidateQueryOnStateChange, viseronAPI } from "lib/api/client";
import * as types from "lib/types";

type CameraRequest = {
  camera_identifier: string;
  failed?: boolean;
};

async function getCamera({ camera_identifier, failed }: CameraRequest) {
  const response = await viseronAPI.get(
    `camera/${camera_identifier}`,
    failed ? { params: { failed: true } } : undefined,
  );
  return response.data;
}

export function useCamera<T extends boolean = false>(
  camera_identifier: string,
  failed?: T,
  configOptions?: Omit<
    UseQueryOptions<
      T extends true
        ? types.Camera | types.FailedCamera
        : T extends undefined
          ? types.Camera
          : types.Camera,
      types.APIErrorResponse
    >,
    "queryKey" | "queryFn"
  >,
) {
  useInvalidateQueryOnStateChange([
    {
      entityId: `binary_sensor.${camera_identifier}_connected`,
      queryKey: ["camera", camera_identifier],
    },
    {
      entityId: `binary_sensor.${camera_identifier}_still_image_available`,
      queryKey: ["camera", camera_identifier],
    },
    {
      entityId: `toggle.${camera_identifier}_connection`,
      queryKey: ["camera", camera_identifier],
    },
    {
      entityId: `sensor.${camera_identifier}_access_token`,
      queryKey: ["camera", camera_identifier],
    },
    {
      entityId: `toggle.${camera_identifier}_manual_recording`,
      queryKey: ["camera", camera_identifier],
    },
    {
      entityId: `toggle.${camera_identifier}_manual_recording`,
      queryKey: ["cameras"],
    },
  ]);

  return useQuery({
    queryKey: ["camera", camera_identifier],
    queryFn: async () => getCamera({ camera_identifier, failed }),
    ...configOptions,
  });
}

type CameraManualRecordingVariables = {
  camera: types.Camera;
  action: "start" | "stop";
};

async function manualRecording({
  camera,
  action,
}: CameraManualRecordingVariables) {
  const response = await viseronAPI.post<types.APISuccessResponse>(
    `/camera/${camera.identifier}/manual_recording`,
    {
      action,
    },
  );
  return response.data;
}

export const useCameraManualRecording = () => {
  const toast = useToast();
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    CameraManualRecordingVariables
  >({
    mutationFn: manualRecording,
    onSuccess: async (_data, variables, _context) => {
      toast.success(
        `Recording ${variables.action === "start" ? "started" : "stopped"} for camera ${variables.camera.name}`,
      );
    },
    onError: async (error, variables, _context) => {
      toast.error(
        error.response && error.response.data.error
          ? `Error ${variables.action === "start" ? "starting" : "stopping"} recording: ${error.response.data.error}`
          : `An error occurred: ${error.message}`,
      );
    },
  });
};

type CameraStartStopVariables = {
  camera: types.Camera;
  action: "start" | "stop";
};

async function startStopCamera({ camera, action }: CameraStartStopVariables) {
  const response = await viseronAPI.post<types.APISuccessResponse>(
    `/camera/${camera.identifier}/${action}`,
  );
  return response.data;
}

export const useCameraStartStop = () => {
  const toast = useToast();
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    CameraStartStopVariables
  >({
    mutationFn: startStopCamera,
    onSuccess: async (_data, variables, _context) => {
      toast.success(
        `Camera ${variables.action === "start" ? "started" : "stopped"}: ${variables.camera.name}`,
      );
    },
    onError: async (error, variables, _context) => {
      toast.error(
        error.response && error.response.data.error
          ? `Error ${variables.action === "start" ? "starting" : "stopping"} camera: ${error.response.data.error}`
          : `An error occurred: ${error.message}`,
      );
    },
  });
};
