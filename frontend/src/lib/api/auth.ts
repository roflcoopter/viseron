import { useMutation } from "react-query";

import { useSnackbar } from "context/SnackbarContext";
import { clientId, viseronAPI } from "lib/api/client";
import { StoreTokensParams, loadTokens, storeTokens } from "lib/api/tokens";
import * as types from "lib/types";

interface AuthCreateVariables {
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
}: AuthCreateVariables) {
  const response = await viseronAPI.post(`/auth/create`, {
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
    types.APIErrorResponse,
    AuthCreateVariables
  >({
    mutationFn: authCreate,
    onSuccess: async (_data, _variables, _context) => {
      snackbar.showSnackbar("User created successfully", "success");
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

interface AuthLoginVariables {
  username: string;
  password: string;
}

async function authLogin({ username, password }: AuthLoginVariables) {
  const response = await viseronAPI.post("/auth/login", {
    username,
    password,
    client_id: clientId(),
  });
  return response.data;
}

export const useAuthLogin = (
  onSuccess?: (
    data: types.APISuccessResponse,
    variables: AuthLoginVariables
  ) => Promise<unknown> | void
) => {
  const snackbar = useSnackbar();
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    AuthLoginVariables
  >({
    mutationFn: authLogin,
    onSuccess: async (data, variables, _context) => {
      snackbar.showSnackbar("Successfully logged in", "success");
      if (onSuccess) {
        await onSuccess(data, variables);
      }
    },
  });
};

interface AuthTokenVariables {
  grant_type: string;
  refresh_token: string;
  client_id: string;
}

export async function authToken({
  grant_type,
  refresh_token,
  client_id,
}: AuthTokenVariables): Promise<types.AuthTokenResponse> {
  const response = await viseronAPI.post("/auth/token", {
    grant_type,
    refresh_token,
    client_id,
  });
  const storedTokens = loadTokens();
  const tokens: StoreTokensParams = {
    access_token: response.data.access_token,
    refresh_token: storedTokens.refresh_token,
    token_type: response.data.token_type,
    expires_in: response.data.expires_in,
  };
  tokens.expires_in = response.data.expires_in;
  storeTokens(tokens);
  return response.data;
}
