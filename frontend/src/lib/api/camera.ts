import { UseQueryOptions, useQuery } from "@tanstack/react-query";

import { viseronAPI } from "lib/api/client";
import * as types from "lib/types";

type CameraVariables = {
  camera_identifier: string;
  configOptions?: UseQueryOptions<types.Camera, types.APIErrorResponse>;
};
type CameraRequest = {
  camera_identifier: string;
};
async function camera({ camera_identifier }: CameraRequest) {
  const response = await viseronAPI.get<types.Camera>(
    `camera/${camera_identifier}`
  );
  return response.data;
}

export const useCamera = ({
  camera_identifier,
  configOptions,
}: CameraVariables) =>
  useQuery<types.Camera, types.APIErrorResponse>(
    ["camera", camera_identifier],
    async () => camera({ camera_identifier }),
    configOptions
  );
