import { UseQueryOptions, useMutation, useQuery } from "@tanstack/react-query";

import { useToast } from "hooks/UseToast";
import { clientId, viseronAPI } from "lib/api/client";
import { clearTokens, storeTokens } from "lib/tokens";
import * as types from "lib/types";

interface AuthCreateVariables {
  name: string;
  username: string;
  password: string;
  role?: "admin" | "write" | "read";
}

async function authCreate({
  name,
  username,
  password,
  role,
}: AuthCreateVariables) {
  const response = await viseronAPI.post(`/auth/create`, {
    name,
    username,
    password,
    role,
  });
  return response.data;
}

export const useAuthCreate = () => {
  const toast = useToast();
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    AuthCreateVariables
  >({
    mutationFn: authCreate,
    onSuccess: async (_data, _variables, _context) => {
      toast.success("User created successfully");
    },
    onError: async (error, _variables, _context) => {
      toast.error(
        error.response && error.response.data.error
          ? `Error creating user: ${error.response.data.error}`
          : `An error occurred: ${error.message}`,
      );
    },
  });
};

type AuthUserRequest = {
  username: string;
};

type AuthUserVariables = {
  username: string;
  configOptions?: Omit<
    UseQueryOptions<types.AuthUserResponse, types.APIErrorResponse>,
    "queryKey" | "queryFn"
  >;
};

async function authUser({ username }: AuthUserRequest) {
  const response = await viseronAPI.get<types.AuthUserResponse>(
    `/auth/user/${username}`,
  );
  return response.data;
}

export const useAuthUser = ({ username, configOptions }: AuthUserVariables) =>
  useQuery({
    queryKey: ["auth", "user", username],
    queryFn: async () => authUser({ username }),
    ...configOptions,
  });

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
  const toast = useToast();
  return useMutation<
    types.AuthLoginResponse,
    types.APIErrorResponse,
    AuthLoginVariables
  >({
    mutationFn: authLogin,
    onSuccess: async (data, _variables, _context) => {
      storeTokens(data);
      toast.success("Successfully logged in");
    },
  });
};

async function authLogout() {
  const response = await viseronAPI.post("/auth/logout");
  return response.data;
}

export const useAuthLogout = () =>
  useMutation<types.APISuccessResponse, types.APIErrorResponse>({
    mutationFn: authLogout,
    onSuccess: async (_data, _variables, _context) => {
      clearTokens();
    },
  });

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
  const response =
    await viseronAPI.get<types.AuthEnabledResponse>("/auth/enabled");
  return response.data;
}

export const useAuthEnabled = () =>
  useQuery({
    queryKey: ["auth", "enabled"],
    queryFn: async () => authEnabled(),
  });
