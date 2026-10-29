import { useMutation, useQuery } from "@tanstack/react-query";

import * as onvif_types from "lib/api/actions/onvif/types";
import { viseronAPI } from "lib/api/client";
import * as types from "lib/types";

const IMAGING = "imaging";
const ONVIF_IMAGING_BASE_PATH = `actions/onvif/${IMAGING}`;

// CAPABILITIES OPERATIONS --------------------------------------------------------------
// //////////////////////////////////////////////////////////////////////////////////////

// Get Imaging Capabilities
const CAPABILITIES = "capabilities";
async function getImagingCapabilities(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_IMAGING_BASE_PATH}/${cameraIdentifier}/${CAPABILITIES}`,
  );
  return response.data;
}

export function useGetImagingCapabilities(cameraIdentifier: string) {
  return useQuery<
    onvif_types.ServiceCapabilitiesResponse,
    types.APIErrorResponse
  >({
    queryKey: [IMAGING, CAPABILITIES, cameraIdentifier],
    queryFn: () => getImagingCapabilities(cameraIdentifier),
    enabled: !!cameraIdentifier,
  });
}

// SETTINGS OPERATIONS ------------------------------------------------------------------
// //////////////////////////////////////////////////////////////////////////////////////

// Get Imaging Settings
const SETTINGS = "settings";
async function getImagingSettings(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_IMAGING_BASE_PATH}/${cameraIdentifier}/${SETTINGS}`,
  );
  return response.data;
}

export function useGetImagingSettings(cameraIdentifier: string) {
  return useQuery<onvif_types.ImagingSettingsResponse, types.APIErrorResponse>({
    queryKey: [IMAGING, SETTINGS, cameraIdentifier],
    queryFn: () => getImagingSettings(cameraIdentifier),
    enabled: !!cameraIdentifier,
  });
}

// Set Imaging Settings
async function setImagingSettings(
  cameraIdentifier: string,
  settings: any,
  forcePersistence: boolean = true,
) {
  const response = await viseronAPI.put(
    `${ONVIF_IMAGING_BASE_PATH}/${cameraIdentifier}/${SETTINGS}`,
    {
      settings,
      force_persistence: forcePersistence,
    },
  );
  return response.data;
}

export function useSetImagingSettings(cameraIdentifier: string) {
  return useMutation({
    mutationFn: ({
      settings,
      forcePersistence = false,
    }: {
      settings: any;
      forcePersistence?: boolean;
    }) => setImagingSettings(cameraIdentifier, settings, forcePersistence),
  });
}

// Get Imaging Options
const OPTIONS = "options";
async function getImagingOptions(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_IMAGING_BASE_PATH}/${cameraIdentifier}/${OPTIONS}`,
  );
  return response.data;
}

export function useGetImagingOptions(cameraIdentifier: string) {
  return useQuery<onvif_types.ImagingOptionsResponse, types.APIErrorResponse>({
    queryKey: [IMAGING, OPTIONS, cameraIdentifier],
    queryFn: () => getImagingOptions(cameraIdentifier),
    enabled: !!cameraIdentifier,
  });
}

// PRESETS OPERATIONS -------------------------------------------------------------------
// //////////////////////////////////////////////////////////////////////////////////////

// Get Imaging Presets
const PRESETS = "presets";
async function getImagingPresets(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_IMAGING_BASE_PATH}/${cameraIdentifier}/${PRESETS}`,
  );
  return response.data;
}

export function useGetImagingPresets(cameraIdentifier: string) {
  return useQuery<onvif_types.ImagingPresetsResponse, types.APIErrorResponse>({
    queryKey: [IMAGING, PRESETS, cameraIdentifier],
    queryFn: () => getImagingPresets(cameraIdentifier),
    enabled: !!cameraIdentifier,
  });
}

// Set Current Imaging Preset
const SET_CURRENT_PRESET = "set_current_preset";
async function setCurrentImagingPreset(
  cameraIdentifier: string,
  presetToken: string,
) {
  const response = await viseronAPI.put(
    `${ONVIF_IMAGING_BASE_PATH}/${cameraIdentifier}/${SET_CURRENT_PRESET}`,
    {
      preset_token: presetToken,
    },
  );
  return response.data;
}

export function useSetCurrentImagingPreset(cameraIdentifier: string) {
  return useMutation({
    mutationFn: (presetToken: string) =>
      setCurrentImagingPreset(cameraIdentifier, presetToken),
  });
}

// FOCUS OPERATIONS ---------------------------------------------------------------------
// //////////////////////////////////////////////////////////////////////////////////////

// Get Move Options
const MOVE_OPTIONS = "move_options";
async function getImagingMoveOptions(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_IMAGING_BASE_PATH}/${cameraIdentifier}/${MOVE_OPTIONS}`,
  );
  return response.data;
}

export function useGetImagingMoveOptions(cameraIdentifier: string) {
  return useQuery<
    onvif_types.ImagingMoveOptionsResponse,
    types.APIErrorResponse
  >({
    queryKey: [IMAGING, MOVE_OPTIONS, cameraIdentifier],
    queryFn: () => getImagingMoveOptions(cameraIdentifier),
    enabled: !!cameraIdentifier,
    retry: false, // Don't retry on error
    staleTime: Infinity,
  });
}

// Move Focus
const MOVE = "move";
async function moveFocusImaging(
  cameraIdentifier: string,
  focus: onvif_types.ImagingMoveParams,
) {
  const response = await viseronAPI.post(
    `${ONVIF_IMAGING_BASE_PATH}/${cameraIdentifier}/${MOVE}`,
    {
      focus,
    },
  );
  return response.data;
}

export function useMoveFocusImaging(cameraIdentifier: string) {
  return useMutation({
    mutationFn: (move: onvif_types.ImagingMoveParams) =>
      moveFocusImaging(cameraIdentifier, move),
  });
}

// Stop Focus Move
const STOP = "stop";
async function stopFocusImaging(cameraIdentifier: string) {
  const response = await viseronAPI.post(
    `${ONVIF_IMAGING_BASE_PATH}/${cameraIdentifier}/${STOP}`,
    {},
  );
  return response.data;
}

export function useStopFocusImaging(cameraIdentifier: string) {
  return useMutation({
    mutationFn: () => stopFocusImaging(cameraIdentifier),
  });
}
