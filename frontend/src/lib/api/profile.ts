import { useMutation, useQuery } from "@tanstack/react-query";

import { useToast } from "hooks/UseToast";
import queryClient, { viseronAPI } from "lib/api/client";
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
};
async function profileUpdatePreferences({
  timezone,
}: ProfileUpdatePreferencesVariables) {
  const response = await viseronAPI.put("/profile/preferences", {
    timezone,
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
