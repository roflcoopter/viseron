import axios, { AxiosError } from "axios";
import { useMutation } from "react-query";

import { useSnackbar } from "context/SnackbarContext";
import { API_V1_URL } from "lib/api";
import * as types from "lib/types";

interface Onboarding {
  name: string;
  username: string;
  password: string;
  group?: string;
}

async function onboarding({ name, username, password }: Onboarding) {
  const response = await axios.post(`${API_V1_URL}/onboarding`, {
    name,
    username,
    password,
  });
  return response.data;
}

export const useOnboarding = () => {
  const snackbar = useSnackbar();
  return useMutation<
    types.APISuccessResponse,
    AxiosError<types.APIErrorResponse>,
    Onboarding
  >({
    mutationFn: onboarding,
    onSuccess: async (_data, _variables, _context) => {
      snackbar.showSnackbar("User created successfully", "success");
    },
    onError: async (
      error: AxiosError<types.APIErrorResponse>,
      _variables: Onboarding,
      _context
    ) => {
      snackbar.showSnackbar(
        error.response && error.response.data.error
          ? `Error creating user: ${error.response.data.error}`
          : `An error occurred: ${error.message}`,
        "error"
      );
    },
  });
};
