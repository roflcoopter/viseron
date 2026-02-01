import { useQuery } from "@tanstack/react-query";

import * as onvif_types from "lib/api/actions/onvif/types";
import { viseronAPI } from "lib/api/client";
import * as types from "lib/types";

const MEDIA = "media";
const ONVIF_MEDIA_BASE_PATH = `actions/onvif/${MEDIA}`;

// CAPABILITIES OPERATIONS --------------------------------------------------------------
// //////////////////////////////////////////////////////////////////////////////////////

// Get Media Capabilities
const CAPABILITIES = "capabilities";
async function getMediaCapabilities(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_MEDIA_BASE_PATH}/${cameraIdentifier}/${CAPABILITIES}`,
  );
  return response.data;
}

export function useGetMediaCapabilities(cameraIdentifier: string) {
  return useQuery<
    onvif_types.ServiceCapabilitiesResponse,
    types.APIErrorResponse
  >({
    queryKey: [MEDIA, CAPABILITIES, cameraIdentifier],
    queryFn: () => getMediaCapabilities(cameraIdentifier),
    enabled: !!cameraIdentifier,
  });
}

// PROFILES OPERATIONS ------------------------------------------------------------------
// //////////////////////////////////////////////////////////////////////////////////////

// Get Device Information
const PROFILES = "profiles";
async function getMediaProfiles(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_MEDIA_BASE_PATH}/${cameraIdentifier}/${PROFILES}`,
  );
  return response.data;
}

export function useGetMediaProfiles(cameraIdentifier: string) {
  return useQuery<onvif_types.MediaProfilesResponse, types.APIErrorResponse>({
    queryKey: [MEDIA, PROFILES, cameraIdentifier],
    queryFn: () => getMediaProfiles(cameraIdentifier),
    enabled: !!cameraIdentifier,
  });
}
