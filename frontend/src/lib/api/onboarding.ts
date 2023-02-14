import { useMutation } from "@tanstack/react-query";

import { useSnackbar } from "context/SnackbarContext";
import queryClient, { clientId, viseronAPI } from "lib/api/client";
import { storeTokens } from "lib/api/tokens";
import * as types from "lib/types";

type OnboardingVariables = {
  name: string;
  username: string;
  password: string;
};

async function onboarding({ name, username, password }: OnboardingVariables) {
  const response = await viseronAPI.post<types.OnboardingResponse>(
    "/onboarding",
    {
      client_id: clientId(),
      name,
      username,
      password,
    }
  );
  return response.data;
}

export const useOnboarding = () => {
  const snackbar = useSnackbar();
  return useMutation<
    types.OnboardingResponse,
    types.APIErrorResponse,
    OnboardingVariables
  >({
    mutationFn: onboarding,
    onSuccess: async (data, _variables, _context) => {
      storeTokens(data);
      snackbar.showSnackbar("User created successfully", "success");
      queryClient.invalidateQueries(["auth"]);
    },
    onError: async (error, _variables, _context) => {
      snackbar.showSnackbar(
        error.response && error.response.data.error
          ? `Error creating user: ${error.response.data.error}`
          : `An error occurred: ${error.message}`,
        "error"
      );
    },
  });
};
