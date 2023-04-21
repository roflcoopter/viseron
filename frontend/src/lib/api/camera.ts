import { UseQueryOptions, useQuery } from "@tanstack/react-query";

import { viseronAPI } from "lib/api/client";
import * as types from "lib/types";

type CameraRequest = {
  camera_identifier: string;
  failed?: boolean;
};

async function camera({ camera_identifier, failed }: CameraRequest) {
  const response = await viseronAPI.get(
    `camera/${camera_identifier}`,
    failed ? { params: { failed: true } } : undefined
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
  >
) {
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
    configOptions
  );
}
