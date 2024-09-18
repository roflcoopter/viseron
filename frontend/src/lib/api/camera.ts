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
      entityId: `toggle.${camera_identifier}_connection`,
      queryKey: ["camera", camera_identifier],
    },
    {
      entityId: `sensor.${camera_identifier}_access_token`,
      queryKey: ["camera", camera_identifier],
    },
  ]);

  return useQuery({
    queryKey: ["camera", camera_identifier],
    queryFn: async () => camera({ camera_identifier, failed }),
    ...configOptions,
  });
}
