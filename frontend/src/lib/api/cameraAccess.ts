import { useMutation, useQuery } from "@tanstack/react-query";

import { useToast } from "hooks/UseToast";
import queryClient, { viseronAPI } from "lib/api/client";
import * as types from "lib/types";

async function cameraAccessConfig() {
  const response =
    await viseronAPI.get<types.CameraAccessConfigResponse>("/cameraaccess");
  return response.data;
}

export const useCameraAccessConfig = () =>
  useQuery({
    queryKey: ["cameraaccess", "config"],
    queryFn: async () => cameraAccessConfig(),
  });

async function saveCameraAccessConfig(config: types.CameraAccessConfig) {
  const response = await viseronAPI.put<types.CameraAccessSaveResponse>(
    "/cameraaccess",
    { config },
  );
  return response.data;
}

export const useSaveCameraAccessConfig = () => {
  const toast = useToast();
  return useMutation<
    types.CameraAccessSaveResponse,
    types.APIErrorResponse,
    types.CameraAccessConfig
  >({
    mutationFn: saveCameraAccessConfig,
    onSuccess: async () => {
      toast.success("Camera access saved");
      queryClient.invalidateQueries({ queryKey: ["cameraaccess", "config"] });
      queryClient.invalidateQueries({ queryKey: ["auth", "users"] });
    },
    onError: async (error) => {
      toast.error(
        error.response && error.response.data.error
          ? `Error saving camera access: ${error.response.data.error}`
          : `An error occurred: ${error.message}`,
      );
    },
  });
};
