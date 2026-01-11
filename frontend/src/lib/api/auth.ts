import { UseQueryOptions, useMutation, useQuery } from "@tanstack/react-query";

import { useToast } from "hooks/UseToast";
import queryClient, { clientId, viseronAPI } from "lib/api/client";
import { clearTokens, setManualLogout, storeTokens } from "lib/tokens";
import * as types from "lib/types";

export const ROLE_LABELS: Record<string, string> = {
  admin: "Administrator",
  read: "Read Only",
  write: "Read & Write",
};

interface AuthCreateVariables {
  name: string;
  username: string;
  password: string;
  role: types.AuthUserResponse["role"];
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
      queryClient.invalidateQueries({
        queryKey: ["auth", "users"],
      });
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

async function authUsers() {
  const response = await viseronAPI.get<types.AuthUsersResponse>("/auth/users");
  return response.data;
}

export const useAuthUsers = () =>
  useQuery({
    queryKey: ["auth", "users"],
    queryFn: async () => authUsers(),
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

export const useAuthLogin = () =>
  useMutation<
    types.AuthLoginResponse,
    types.APIErrorResponse,
    AuthLoginVariables
  >({
    mutationFn: authLogin,
    onSuccess: async (data, _variables, _context) => {
      storeTokens(data);
      // Reset manual logout flag on successful login
      setManualLogout(false);
    },
  });

async function authLogout() {
  const response = await viseronAPI.post("/auth/logout");
  return response.data;
}

export const useAuthLogout = () =>
  useMutation<types.APISuccessResponse, types.APIErrorResponse>({
    mutationFn: authLogout,
    onSuccess: async (_data, _variables, _context) => {
      // Set flag to indicate this is a manual logout
      setManualLogout(true);
      clearTokens();
      // Clear all queries except auth.enabled to prevent unnecessary refetching
      queryClient.removeQueries({
        predicate: (query) => {
          const isAuthEnabled =
            query.queryKey[0] === "auth" && query.queryKey[1] === "enabled";
          return !isAuthEnabled;
        },
      });
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

async function authDelete(user: types.AuthUserResponse) {
  const response = await viseronAPI.delete(`/auth/user/${user.id}`);
  return response.data;
}

export const useAuthDelete = () => {
  const toast = useToast();
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    types.AuthUserResponse
  >({
    mutationFn: authDelete,
    onSuccess: async (_data, user, _context) => {
      toast.success(`User "${user.username}" deleted successfully`);
      queryClient.invalidateQueries({
        queryKey: ["auth", "users"],
      });
    },
    onError: async (error, user, _context) => {
      toast.error(
        error.response && error.response.data.error
          ? `Error deleting user "${user.username}": ${error.response.data.error}`
          : `An error occurred: ${error.message}`,
      );
    },
  });
};

async function authAdminChangePassword(
  user: types.AuthUserResponse,
  newPassword: string,
) {
  const response = await viseronAPI.put(
    `/auth/user/${user.id}/admin_change_password`,
    {
      new_password: newPassword,
    },
  );
  return response.data;
}

export const useAuthAdminChangePassword = () => {
  const toast = useToast();
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    { user: types.AuthUserResponse; newPassword: string }
  >({
    mutationFn: ({ user, newPassword }) =>
      authAdminChangePassword(user, newPassword),
    onSuccess: async (_data, variables, _context) => {
      toast.success(
        `Password for user "${variables.user.username}" changed successfully`,
      );
    },
    onError: async (error, variables, _context) => {
      toast.error(
        error.response && error.response.data.error
          ? `Error changing password for user "${variables.user.username}": ${error.response.data.error}`
          : `An error occurred: ${error.message}`,
      );
    },
  });
};

async function authUpdateUser({
  id,
  name,
  username,
  role,
  assigned_cameras,
}: types.AuthUserResponse) {
  const response = await viseronAPI.put(`/auth/user/${id}`, {
    name,
    username,
    role,
    assigned_cameras:
      assigned_cameras && assigned_cameras.length > 0 ? assigned_cameras : null,
  });
  return response.data;
}

export const useAuthUpdateUser = () => {
  const toast = useToast();
  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    types.AuthUserResponse
  >({
    mutationFn: authUpdateUser,
    onSuccess: async (_data, user, _context) => {
      toast.success(`User "${user.username}" updated successfully`);
      queryClient.invalidateQueries({
        queryKey: ["auth", "users"],
      });
    },
    onError: async (error, user, _context) => {
      toast.error(
        error.response && error.response.data.error
          ? `Error updating user "${user.username}": ${error.response.data.error}`
          : `An error occurred: ${error.message}`,
      );
    },
  });
};
