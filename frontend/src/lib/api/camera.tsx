import { useQuery } from "@tanstack/react-query";

import * as types from "lib/types";

import { viseronAPI } from "./client";

interface CameraVariables {
  camera_identifier: string;
}
async function camera({ camera_identifier }: CameraVariables) {
  const response = await viseronAPI.get<types.Camera>(
    `camera/${camera_identifier}`
  );
  return response.data;
}

export const useCamera = ({ camera_identifier }: CameraVariables) =>
  useQuery<types.Camera, types.APIErrorResponse>(
    ["camera", camera_identifier],
    async () => camera({ camera_identifier })
  );
