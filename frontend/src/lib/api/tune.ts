import {
  UseMutationOptions,
  UseQueryOptions,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { viseronAPI } from "lib/api/client";

export interface TuneConfig {
  [key: string]: any;
}

type TuneVariables = {
  camera_identifier: string;
  configOptions?: Omit<
    UseQueryOptions<TuneConfig, Error>,
    "queryKey" | "queryFn"
  >;
};

export interface UpdateTuneConfigPayload {
  domain: string;
  component: string;
  data: any;
}

async function getTuneConfig(camera_identifier: string) {
  const response = await viseronAPI.get<TuneConfig>(
    `tune/${camera_identifier}`,
  );
  return response.data;
}

async function updateTuneConfig(
  camera_identifier: string,
  payload: UpdateTuneConfigPayload,
) {
  const response = await viseronAPI.put(`tune/${camera_identifier}`, payload);
  return response.data;
}

export const useTuneConfig = ({
  camera_identifier,
  configOptions,
}: TuneVariables) =>
  useQuery({
    queryKey: ["tune", camera_identifier],
    queryFn: () => getTuneConfig(camera_identifier),
    enabled: !!camera_identifier,
    ...configOptions,
  });

export const useUpdateTuneConfig = (
  camera_identifier: string,
  mutationOptions?: Omit<
    UseMutationOptions<any, Error, UpdateTuneConfigPayload>,
    "mutationFn"
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: UpdateTuneConfigPayload) =>
      updateTuneConfig(camera_identifier, payload),
    onSuccess: () => {
      // Invalidate and refetch tune config after successful update
      queryClient.invalidateQueries({
        queryKey: ["tune", camera_identifier],
      });
    },
    ...mutationOptions,
  });
};
