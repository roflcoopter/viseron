import axios, { AxiosError } from "axios";
import { useMutation } from "react-query";

import { useSnackbar } from "context/SnackbarContext";
import { API_V1_URL } from "lib/api";
import * as types from "lib/types";

interface AuthCreateParams {
  name: string;
  username: string;
  password: string;
  group?: string;
}

async function authCreate({
  name,
  username,
  password,
  group,
}: AuthCreateParams) {
  const response = await axios.post(`${API_V1_URL}/auth/create`, {
    name,
    username,
    password,
    group,
  });
  return response.data;
}

export const useAuthCreate = () => {
  const snackbar = useSnackbar();
  return useMutation<
    types.APISuccessResponse,
    AxiosError<types.APIErrorResponse>,
    AuthCreateParams
  >({
    mutationFn: authCreate,
    onSuccess: async (_data, _variables, _context) => {
      snackbar.showSnackbar("User created successfully", "success");
    },
    onError: async (
      error: AxiosError<types.APIErrorResponse>,
      _variables: AuthCreateParams,
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
