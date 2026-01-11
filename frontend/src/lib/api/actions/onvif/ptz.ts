import { useMutation, useQuery } from "@tanstack/react-query";

import * as onvif_types from "lib/api/actions/onvif/types";
import { viseronAPI } from "lib/api/client";
import * as types from "lib/types";

const ONVIF_PTZ_BASE_PATH = "actions/onvif/ptz";

// Get User-Defined PTZ Config
async function getPtzConfig(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/user_config`,
  );
  return response.data;
}

export function useGetPtzConfig(cameraIdentifier: string) {
  return useQuery<onvif_types.PtzConfigResponse, types.APIErrorResponse>({
    queryKey: ["ptz", "user_config", cameraIdentifier],
    queryFn: () => getPtzConfig(cameraIdentifier),
    enabled: !!cameraIdentifier,
    retry: false, // Don't retry on error - camera either supports PTZ or doesn't
    staleTime: Infinity, // Cache the result indefinitely - PTZ support doesn't change
  });
}

// Get PTZ Nodes
async function getPtzNodes(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/nodes`,
  );
  return response.data;
}

export function useGetPtzNodes(cameraIdentifier: string) {
  return useQuery<onvif_types.PtzNodesResponse, types.APIErrorResponse>({
    queryKey: ["ptz", "nodes", cameraIdentifier],
    queryFn: () => getPtzNodes(cameraIdentifier),
    enabled: !!cameraIdentifier,
  });
}

// Get PTZ Configurations
async function getPtzConfigurations(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/configurations`,
  );
  return response.data;
}

export function useGetPtzConfigurations(cameraIdentifier: string) {
  return useQuery<
    onvif_types.PtzConfigurationsResponse,
    types.APIErrorResponse
  >({
    queryKey: ["ptz", "configurations", cameraIdentifier],
    queryFn: () => getPtzConfigurations(cameraIdentifier),
    enabled: !!cameraIdentifier,
  });
}

// Get PTZ Status
async function getPtzStatus(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/status`,
  );
  return response.data;
}

export function useGetPtzStatus(cameraIdentifier: string) {
  return useQuery<onvif_types.PtzStatusResponse, types.APIErrorResponse>({
    queryKey: ["ptz", "status", cameraIdentifier],
    queryFn: () => getPtzStatus(cameraIdentifier),
    enabled: !!cameraIdentifier,
    staleTime: 1000 * 5, // 5 seconds
  });
}

// Get PTZ Presets
async function getPtzPresets(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/presets`,
  );
  return response.data;
}

export function useGetPtzPresets(
  cameraIdentifier: string,
  ptzSupport?: "onvif" | null,
) {
  return useQuery<onvif_types.PtzPresetsResponse, types.APIErrorResponse>({
    queryKey: ["ptz", "presets", cameraIdentifier],
    queryFn: () => getPtzPresets(cameraIdentifier),
    enabled: !!cameraIdentifier && ptzSupport === "onvif",
    retry: false, // Don't retry on error - camera either supports PTZ or doesn't
    staleTime: Infinity, // Cache the result indefinitely - PTZ support doesn't change
  });
}

// PTZ Continuous Move
async function ptzContinuousMove(
  cameraIdentifier: string,
  params: onvif_types.PtzContinuousMoveParams,
) {
  const response = await viseronAPI.post(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/continuous_move`,
    { continuous: params },
  );
  return response.data;
}

export function usePtzContinuousMove() {
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    { cameraIdentifier: string; params: onvif_types.PtzContinuousMoveParams }
  >({
    mutationFn: ({ cameraIdentifier, params }) =>
      ptzContinuousMove(cameraIdentifier, params),
  });
}

// PTZ Relative Move
async function ptzRelativeMove(
  cameraIdentifier: string,
  params: onvif_types.PtzRelativeMoveParams,
) {
  const response = await viseronAPI.post(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/relative_move`,
    { relative: params },
  );
  return response.data;
}

export function usePtzRelativeMove() {
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    { cameraIdentifier: string; params: onvif_types.PtzRelativeMoveParams }
  >({
    mutationFn: ({ cameraIdentifier, params }) =>
      ptzRelativeMove(cameraIdentifier, params),
  });
}

async function ptzAbsoluteMove(
  cameraIdentifier: string,
  params: onvif_types.PtzAbsoluteMoveParams,
) {
  const response = await viseronAPI.post(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/absolute_move`,
    { absolute: params },
  );
  return response.data;
}

export function usePtzAbsoluteMove() {
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    { cameraIdentifier: string; params: onvif_types.PtzAbsoluteMoveParams }
  >({
    mutationFn: ({ cameraIdentifier, params }) =>
      ptzAbsoluteMove(cameraIdentifier, params),
  });
}

// PTZ Stop
async function ptzStop(cameraIdentifier: string) {
  const response = await viseronAPI.post(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/stop`,
    {},
  );
  return response.data;
}

export function usePtzStop() {
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    { cameraIdentifier: string }
  >({
    mutationFn: ({ cameraIdentifier }) => ptzStop(cameraIdentifier),
  });
}

// PTZ Go Home
async function ptzGoHome(cameraIdentifier: string) {
  const response = await viseronAPI.post(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/home`,
    {},
  );
  return response.data;
}

export function usePtzGoHome() {
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    { cameraIdentifier: string }
  >({
    mutationFn: ({ cameraIdentifier }) => ptzGoHome(cameraIdentifier),
  });
}

// PTZ Set Home Position
async function ptzSetHome(cameraIdentifier: string) {
  const response = await viseronAPI.put(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/set_home`,
    {},
  );
  return response.data;
}

export function usePtzSetHome() {
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    { cameraIdentifier: string }
  >({
    mutationFn: ({ cameraIdentifier }) => ptzSetHome(cameraIdentifier),
  });
}

// PTZ Goto Preset
async function ptzGotoPreset(cameraIdentifier: string, presetToken: string) {
  const response = await viseronAPI.post(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/goto_preset`,
    { preset_token: presetToken },
  );
  return response.data;
}

export function usePtzGotoPreset() {
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    { cameraIdentifier: string; presetToken: string }
  >({
    mutationFn: ({ cameraIdentifier, presetToken }) =>
      ptzGotoPreset(cameraIdentifier, presetToken),
  });
}

// PTZ Set Preset
async function ptzSetPreset(cameraIdentifier: string, presetName: string) {
  const response = await viseronAPI.put(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/set_preset`,
    { preset_name: presetName },
  );
  return response.data;
}

export function usePtzSetPreset() {
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    { cameraIdentifier: string; presetName: string }
  >({
    mutationFn: ({ cameraIdentifier, presetName }) =>
      ptzSetPreset(cameraIdentifier, presetName),
  });
}

// PTZ Remove Preset
async function ptzRemovePreset(cameraIdentifier: string, presetToken: string) {
  const response = await viseronAPI.delete(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/remove_preset?preset_token=${presetToken}`,
  );
  return response.data;
}

export function usePtzRemovePreset() {
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    { cameraIdentifier: string; presetToken: string }
  >({
    mutationFn: ({ cameraIdentifier, presetToken }) =>
      ptzRemovePreset(cameraIdentifier, presetToken),
  });
}
