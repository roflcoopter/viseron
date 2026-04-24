import { useMutation, useQuery } from "@tanstack/react-query";

import { useToast } from "hooks/UseToast";
import queryClient, { viseronAPI } from "lib/api/client";
import { clearTokens, setManualLogout } from "lib/tokens";
import * as types from "lib/types";

// Timezones
export type ProfileAvailableTimezonesResponse = {
  timezones: string[];
};
async function profileAvailableTimezones() {
  const response = await viseronAPI.get<ProfileAvailableTimezonesResponse>(
    "/profile/available_timezones",
  );
  return response.data;
}
export const useProfileAvailableTimezones = () =>
  useQuery({
    queryKey: ["profile", "available_timezones"],
    queryFn: async () => profileAvailableTimezones(),
  });

// Update preferences
export type ProfileUpdatePreferencesVariables = {
  timezone: string | null;
  date_format: string | null;
  time_format: string | null;
};
async function profileUpdatePreferences({
  timezone,
  date_format,
  time_format,
}: ProfileUpdatePreferencesVariables) {
  const response = await viseronAPI.put("/profile/preferences", {
    timezone,
    date_format,
    time_format,
  });
  return response.data;
}
export const useProfileUpdatePreferences = () => {
  const toast = useToast();
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    ProfileUpdatePreferencesVariables
  >({
    mutationFn: profileUpdatePreferences,
    onSuccess: async (_data, _variables, _context) => {
      toast.success("Preferences updated successfully");
      queryClient.invalidateQueries({
        predicate(query) {
          const isAuthEnabled =
            query.queryKey[0] === "auth" && query.queryKey[1] === "enabled";
          return !isAuthEnabled;
        },
      });
    },
    onError: async (error, _variables, _context) => {
      toast.error(
        error.response && error.response.data.error
          ? `Error updating preferences: ${error.response.data.error}`
          : `An error occurred: ${error.message}`,
      );
    },
  });
};

// Update display name
export type ProfileUpdateDisplayNameVariables = {
  name: string;
};
async function profileUpdateDisplayName({
  name,
}: ProfileUpdateDisplayNameVariables) {
  const trimmed = name.trim();
  const response = await viseronAPI.put("/profile/display_name", {
    name: trimmed,
  });
  return response.data;
}
export const useProfileUpdateDisplayName = () => {
  const toast = useToast();
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    ProfileUpdateDisplayNameVariables
  >({
    mutationFn: profileUpdateDisplayName,
    onSuccess: async (_data, variables, _context) => {
      toast.success(`Display name updated to "${variables.name.trim()}"`);
      queryClient.invalidateQueries({
        queryKey: ["auth", "user"],
      });
    },
    onError: async (error, _variables, _context) => {
      toast.error(
        error.response && error.response.data.error
          ? `Error updating display name: ${error.response.data.error}`
          : `An error occurred: ${error.message}`,
      );
    },
  });
};

// Personal Access Tokens
async function profileAccessTokens() {
  const response = await viseronAPI.get<types.AccessTokensResponse>(
    "/profile/access_tokens",
  );
  return response.data;
}
export const useProfileAccessTokens = () =>
  useQuery({
    queryKey: ["profile", "access_tokens"],
    queryFn: async () => profileAccessTokens(),
  });

export type ProfileCreateAccessTokenVariables = {
  name: string;
  expires_at?: number | null;
};
async function profileCreateAccessToken(
  variables: ProfileCreateAccessTokenVariables,
) {
  const response = await viseronAPI.post<types.AccessTokenCreateResponse>(
    "/profile/access_tokens",
    variables,
  );
  return response.data;
}
export const useProfileCreateAccessToken = () => {
  const toast = useToast();
  return useMutation<
    types.AccessTokenCreateResponse,
    types.APIErrorResponse,
    ProfileCreateAccessTokenVariables
  >({
    mutationFn: profileCreateAccessToken,
    onSuccess: async (_data, _variables, _context) => {
      queryClient.invalidateQueries({
        queryKey: ["profile", "access_tokens"],
      });
    },
    onError: async (error, _variables, _context) => {
      toast.error(
        error.response && error.response.data.error
          ? `Error creating token: ${error.response.data.error}`
          : `An error occurred: ${error.message}`,
      );
    },
  });
};

export type ProfileDeleteAccessTokenVariables = { tokenId: string };
async function profileDeleteAccessToken({
  tokenId,
}: ProfileDeleteAccessTokenVariables) {
  const response = await viseronAPI.delete<types.APISuccessResponse>(
    `/profile/access_tokens/${tokenId}`,
  );
  return response.data;
}
export const useProfileDeleteAccessToken = () => {
  const toast = useToast();
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    ProfileDeleteAccessTokenVariables
  >({
    mutationFn: profileDeleteAccessToken,
    onSuccess: async (_data, _variables, _context) => {
      toast.success("Token revoked");
      queryClient.invalidateQueries({
        queryKey: ["profile", "access_tokens"],
      });
    },
    onError: async (error, _variables, _context) => {
      toast.error(
        error.response && error.response.data.error
          ? `Error revoking token: ${error.response.data.error}`
          : `An error occurred: ${error.message}`,
      );
    },
  });
};

async function profileRevokeAll() {
  const response = await viseronAPI.post<types.APISuccessResponse>(
    "/profile/revoke_all",
  );
  return response.data;
}
export const useProfileRevokeAll = () => {
  const toast = useToast();
  return useMutation<types.APISuccessResponse, types.APIErrorResponse>({
    mutationFn: profileRevokeAll,
    onSuccess: async (_data, _variables, _context) => {
      toast.success("All sessions and tokens revoked");
      setManualLogout(true);
      clearTokens();
      queryClient.removeQueries({
        predicate: (query) => {
          const isAuthEnabled =
            query.queryKey[0] === "auth" && query.queryKey[1] === "enabled";
          return !isAuthEnabled;
        },
      });
    },
    onError: async (error, _variables, _context) => {
      toast.error(
        error.response && error.response.data.error
          ? `Error revoking sessions: ${error.response.data.error}`
          : `An error occurred: ${error.message}`,
      );
    },
  });
};
