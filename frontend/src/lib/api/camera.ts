import { UseQueryOptions, useQuery } from "@tanstack/react-query";

import { useInvalidateQueryOnStateChange, viseronAPI } from "lib/api/client";
import * as types from "lib/types";

type CameraRequest = {
  camera_identifier: string;
  failed?: boolean;
};

async function camera({ camera_identifier, failed }: CameraRequest) {
  const response = await viseronAPI.get(
    `camera/${camera_identifier}`,
    failed ? { params: { failed: true } } : undefined,
  );
  return response.data;
}

export function useCamera<T extends boolean = false>(
  camera_identifier: string,
  failed?: T,
  configOptions?: UseQueryOptions<
    T extends true
      ? types.Camera | types.FailedCamera
      : T extends undefined
        ? types.Camera
        : types.Camera,
    types.APIErrorResponse
  >,
) {
  useInvalidateQueryOnStateChange(
    `binary_sensor.${camera_identifier}_connected`,
    ["camera", camera_identifier],
  );
  useInvalidateQueryOnStateChange(`toggle.${camera_identifier}_connection`, [
    "camera",
    camera_identifier,
  ]);
  useInvalidateQueryOnStateChange(`sensor.${camera_identifier}_access_token`, [
    "camera",
    camera_identifier,
  ]);

  return useQuery<
    T extends true
      ? types.Camera | types.FailedCamera
      : T extends undefined
        ? types.Camera
        : types.Camera,
    types.APIErrorResponse
  >(
    ["camera", camera_identifier],
    async () => camera({ camera_identifier, failed }),
    configOptions,
  );
}
