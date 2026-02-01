import { useMutation, useQuery } from "@tanstack/react-query";

import * as onvif_types from "lib/api/actions/onvif/types";
import { viseronAPI } from "lib/api/client";
import * as types from "lib/types";

const ONVIF_PTZ_BASE_PATH = "actions/onvif/ptz";

// Get User-Defined PTZ Config
const USER_CONFIG = "user_config";
async function getPtzConfig(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/${USER_CONFIG}`,
  );
  return response.data;
}

export function useGetPtzConfig(cameraIdentifier: string) {
  return useQuery<onvif_types.PtzConfigResponse, types.APIErrorResponse>({
    queryKey: ["ptz", USER_CONFIG, cameraIdentifier],
    queryFn: () => getPtzConfig(cameraIdentifier),
    enabled: !!cameraIdentifier,
    retry: false, // Don't retry on error - camera either supports PTZ or doesn't
    staleTime: Infinity, // Cache the result indefinitely - PTZ support doesn't change
  });
}

// Get PTZ Nodes
const NODES = "nodes";
async function getPtzNodes(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/${NODES}`,
  );
  return response.data;
}

export function useGetPtzNodes(cameraIdentifier: string) {
  return useQuery<onvif_types.PtzNodesResponse, types.APIErrorResponse>({
    queryKey: ["ptz", NODES, cameraIdentifier],
    queryFn: () => getPtzNodes(cameraIdentifier),
    enabled: !!cameraIdentifier,
  });
}

// Get PTZ Configurations
const CONFIGURATIONS = "configurations";
async function getPtzConfigurations(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/${CONFIGURATIONS}`,
  );
  return response.data;
}

export function useGetPtzConfigurations(cameraIdentifier: string) {
  return useQuery<
    onvif_types.PtzConfigurationsResponse,
    types.APIErrorResponse
  >({
    queryKey: ["ptz", CONFIGURATIONS, cameraIdentifier],
    queryFn: () => getPtzConfigurations(cameraIdentifier),
    enabled: !!cameraIdentifier,
  });
}

// Get PTZ Status
const STATUS = "status";
async function getPtzStatus(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/${STATUS}`,
  );
  return response.data;
}

export function useGetPtzStatus(cameraIdentifier: string) {
  return useQuery<onvif_types.PtzStatusResponse, types.APIErrorResponse>({
    queryKey: ["ptz", STATUS, cameraIdentifier],
    queryFn: () => getPtzStatus(cameraIdentifier),
    enabled: !!cameraIdentifier,
    staleTime: 1000 * 5, // 5 seconds
  });
}

// Get PTZ Presets
const PRESETS = "presets";
async function getPtzPresets(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/${PRESETS}`,
  );
  return response.data;
}

export function useGetPtzPresets(
  cameraIdentifier: string,
  ptzSupport?: "onvif" | null,
) {
  return useQuery<onvif_types.PtzPresetsResponse, types.APIErrorResponse>({
    queryKey: ["ptz", PRESETS, cameraIdentifier],
    queryFn: () => getPtzPresets(cameraIdentifier),
    enabled: !!cameraIdentifier && ptzSupport === "onvif",
    retry: false, // Don't retry on error - camera either supports PTZ or doesn't
    staleTime: Infinity, // Cache the result indefinitely - PTZ support doesn't change
  });
}

// PTZ Continuous Move
const CONTINUOUS_MOVE = "continuous_move";
async function ptzContinuousMove(
  cameraIdentifier: string,
  params: onvif_types.PtzContinuousMoveParams,
) {
  const response = await viseronAPI.post(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/${CONTINUOUS_MOVE}`,
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
const RELATIVE_MOVE = "relative_move";
async function ptzRelativeMove(
  cameraIdentifier: string,
  params: onvif_types.PtzRelativeMoveParams,
) {
  const response = await viseronAPI.post(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/${RELATIVE_MOVE}`,
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

// PTZ Absolute Move
const ABSOLUTE_MOVE = "absolute_move";
async function ptzAbsoluteMove(
  cameraIdentifier: string,
  params: onvif_types.PtzAbsoluteMoveParams,
) {
  const response = await viseronAPI.post(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/${ABSOLUTE_MOVE}`,
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
const STOP = "stop";
async function ptzStop(cameraIdentifier: string) {
  const response = await viseronAPI.post(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/${STOP}`,
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

// PTZ Goto Home
const GOTO_HOME = "goto_home";
async function ptzGotoHome(cameraIdentifier: string) {
  const response = await viseronAPI.post(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/${GOTO_HOME}`,
    {},
  );
  return response.data;
}

export function usePtzGotoHome() {
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    { cameraIdentifier: string }
  >({
    mutationFn: ({ cameraIdentifier }) => ptzGotoHome(cameraIdentifier),
  });
}

// PTZ Set Home Position
const SET_HOME = "set_home";
async function ptzSetHome(cameraIdentifier: string) {
  const response = await viseronAPI.put(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/${SET_HOME}`,
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
const GOTO_PRESET = "goto_preset";
async function ptzGotoPreset(cameraIdentifier: string, presetToken: string) {
  const response = await viseronAPI.post(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/${GOTO_PRESET}`,
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
const SET_PRESET = "set_preset";
async function ptzSetPreset(cameraIdentifier: string, presetName: string) {
  const response = await viseronAPI.put(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/${SET_PRESET}`,
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
const REMOVE_PRESET = "remove_preset";
const PRESET_TOKEN = "preset_token";
async function ptzRemovePreset(cameraIdentifier: string, presetToken: string) {
  const response = await viseronAPI.delete(
    `${ONVIF_PTZ_BASE_PATH}/${cameraIdentifier}/${REMOVE_PRESET}?${PRESET_TOKEN}=${presetToken}`,
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
