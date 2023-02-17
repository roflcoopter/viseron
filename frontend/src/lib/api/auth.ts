import { UseQueryOptions, useMutation, useQuery } from "@tanstack/react-query";

import { useSnackbar } from "context/SnackbarContext";
import { clientId, viseronAPI } from "lib/api/client";
import { storeTokens } from "lib/tokens";
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

type AuthUserRequest = {
  username: string;
};

type AuthUserVariables = {
  username: string;
  setUser: React.Dispatch<React.SetStateAction<types.AuthUserResponse | null>>;
  configOptions?: UseQueryOptions<
    types.AuthUserResponse,
    types.APIErrorResponse
  >;
};

async function authUser({ username }: AuthUserRequest) {
  const response = await viseronAPI.get<types.AuthUserResponse>(
    `/auth/user/${username}`
  );
  return response.data;
}

export const useAuthUser = ({
  username,
  setUser,
  configOptions,
}: AuthUserVariables) =>
  useQuery<types.AuthUserResponse, types.APIErrorResponse>(
    ["auth", "user", username],
    async () => authUser({ username }),
    {
      onSuccess: async (data) => {
        setUser(data);
      },
      onError: async (_error) => {
        setUser(null);
      },
      ...configOptions,
    }
  );

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

export const useAuthLogin = () => {
  const snackbar = useSnackbar();
  return useMutation<
    types.AuthLoginResponse,
    types.APIErrorResponse,
    AuthLoginVariables
  >({
    mutationFn: authLogin,
    onSuccess: async (data, _variables, _context) => {
      storeTokens(data);
      snackbar.showSnackbar("Successfully logged in", "success");
    },
  });
};

interface AuthTokenVariables {
  grant_type: string;
  client_id: string;
}

export async function authToken({
  grant_type,
  client_id,
}: AuthTokenVariables): Promise<types.AuthTokenResponse> {
  const response = await viseronAPI.post("/auth/token", {
    grant_type,
    client_id,
  });
  storeTokens(response.data);
  return response.data;
}

async function authEnabled() {
  const response = await viseronAPI.get<types.AuthEnabledResponse>(
    "/auth/enabled"
  );
  return response.data;
}

interface AuthEnabledVariables {
  setAuth: React.Dispatch<React.SetStateAction<types.AuthEnabledResponse>>;
}

export const useAuthEnabled = ({ setAuth }: AuthEnabledVariables) =>
  useQuery<types.AuthEnabledResponse, types.APIErrorResponse>(
    ["auth", "enabled"],
    async () => authEnabled(),
    {
      onSuccess: async (data) => {
        setAuth((prevAuth) => {
          if (
            prevAuth.enabled === data.enabled &&
            prevAuth.onboarding_complete === data.onboarding_complete
          ) {
            return prevAuth;
          }
          return data;
        });
      },
    }
  );
