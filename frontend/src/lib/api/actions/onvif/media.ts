import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

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

// Create Media Profile
const CREATE_PROFILE = "create_profile";
async function createMediaProfile(
  cameraIdentifier: string,
  profile: onvif_types.MediaProfileCreateParams,
) {
  const response = await viseronAPI.post(
    `${ONVIF_MEDIA_BASE_PATH}/${cameraIdentifier}/${CREATE_PROFILE}`,
    { profile },
  );
  return response.data;
}

export function useCreateMediaProfile(cameraIdentifier: string) {
  const queryClient = useQueryClient();

  return useMutation<
    onvif_types.MediaProfilesResponse,
    types.APIErrorResponse,
    onvif_types.MediaProfileCreateParams
  >({
    mutationFn: (profile) => createMediaProfile(cameraIdentifier, profile),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [MEDIA, PROFILES, cameraIdentifier],
      });
    },
  });
}

// Delete Media Profile
const DELETE_PROFILE = "delete_profile";
const PROFILE_TOKEN = "profile_token";
async function deleteMediaProfile(
  cameraIdentifier: string,
  profileToken: string,
) {
  const response = await viseronAPI.delete(
    `${ONVIF_MEDIA_BASE_PATH}/${cameraIdentifier}/${DELETE_PROFILE}?${PROFILE_TOKEN}=${profileToken}`,
  );
  return response.data;
}

export function useDeleteMediaProfile(cameraIdentifier: string) {
  const queryClient = useQueryClient();

  return useMutation<
    onvif_types.MediaProfilesResponse,
    types.APIErrorResponse,
    string
  >({
    mutationFn: (profileToken) =>
      deleteMediaProfile(cameraIdentifier, profileToken),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [MEDIA, PROFILES, cameraIdentifier],
      });
    },
  });
}

// URI OPERATIONS -----------------------------------------------------------------------
// //////////////////////////////////////////////////////////////////////////////////////

// Get Media Stream URI
const STREAM_URI = "stream_uri";
async function getMediaStreamUri(
  cameraIdentifier: string,
  params: onvif_types.MediaStreamUriParams,
) {
  const searchParams = new URLSearchParams();

  if (params.token) {
    searchParams.append("token", params.token);
  }
  searchParams.append("stream_type", params.stream_type);
  searchParams.append("protocol", params.protocol);

  const response = await viseronAPI.get(
    `${ONVIF_MEDIA_BASE_PATH}/${cameraIdentifier}/${STREAM_URI}?${searchParams.toString()}`,
  );
  return response.data;
}

export function useGetMediaStreamUri(
  cameraIdentifier: string,
  params: onvif_types.MediaStreamUriParams,
  enabled = true,
) {
  return useQuery<onvif_types.MediaStreamUriResponse, types.APIErrorResponse>({
    queryKey: [
      MEDIA,
      STREAM_URI,
      cameraIdentifier,
      params.token,
      params.stream_type,
      params.protocol,
    ],
    queryFn: () => getMediaStreamUri(cameraIdentifier, params),
    enabled: !!cameraIdentifier && !!params.token && enabled,
  });
}

const SNAPSHOT_URI = "snapshot_uri";
async function getMediaSnapshotUri(
  cameraIdentifier: string,
  profileToken: string,
) {
  const searchParams = new URLSearchParams({ token: profileToken });
  const response = await viseronAPI.get(
    `${ONVIF_MEDIA_BASE_PATH}/${cameraIdentifier}/${SNAPSHOT_URI}?${searchParams.toString()}`,
  );
  return response.data;
}

export function useGetMediaSnapshotUri(
  cameraIdentifier: string,
  profileToken?: string,
  enabled = true,
) {
  return useQuery<onvif_types.MediaSnapshotUriResponse, types.APIErrorResponse>(
    {
      queryKey: [MEDIA, SNAPSHOT_URI, cameraIdentifier, profileToken],
      queryFn: () =>
        getMediaSnapshotUri(cameraIdentifier, profileToken as string),
      enabled: !!cameraIdentifier && !!profileToken && enabled,
    },
  );
}
