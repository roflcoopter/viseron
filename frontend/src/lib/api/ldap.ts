import { useMutation, useQuery } from "@tanstack/react-query";

import { useToast } from "hooks/UseToast";
import queryClient, { viseronAPI } from "lib/api/client";
import * as types from "lib/types";

async function ldapConfig() {
  const response = await viseronAPI.get<types.LDAPConfigResponse>("/ldap");
  return response.data;
}

export const useLDAPConfig = () =>
  useQuery({
    queryKey: ["ldap", "config"],
    queryFn: async () => ldapConfig(),
  });

async function saveLDAPConfig(config: types.LDAPConfig) {
  const response = await viseronAPI.put<types.LDAPSaveResponse>("/ldap", {
    config,
  });
  return response.data;
}

export const useSaveLDAPConfig = () => {
  const toast = useToast();
  return useMutation<
    types.LDAPSaveResponse,
    types.APIErrorResponse,
    types.LDAPConfig
  >({
    mutationFn: saveLDAPConfig,
    onSuccess: async () => {
      toast.success("LDAP settings saved");
      queryClient.invalidateQueries({ queryKey: ["ldap", "config"] });
      queryClient.invalidateQueries({ queryKey: ["auth", "enabled"] });
    },
    onError: async (error) => {
      toast.error(
        error.response && error.response.data.error
          ? `Error saving LDAP settings: ${error.response.data.error}`
          : `An error occurred: ${error.message}`,
      );
    },
  });
};

async function testLDAPConfig({
  config,
  username,
  password,
}: {
  config: types.LDAPConfig;
  username: string;
  password: string;
}) {
  const response = await viseronAPI.post<types.LDAPTestResponse>("/ldap/test", {
    config,
    username,
    password,
  });
  return response.data;
}

export const useTestLDAPConfig = () => {
  const toast = useToast();
  return useMutation<
    types.LDAPTestResponse,
    types.APIErrorResponse,
    { config: types.LDAPConfig; username: string; password: string }
  >({
    mutationFn: testLDAPConfig,
    onSuccess: async () => {
      toast.success("LDAP test successful");
    },
    onError: async (error) => {
      toast.error(
        error.response && error.response.data.error
          ? `LDAP test failed: ${error.response.data.error}`
          : `An error occurred: ${error.message}`,
      );
    },
  });
};
