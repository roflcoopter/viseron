import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as onvif_types from "lib/api/actions/onvif/types";
import { viseronAPI } from "lib/api/client";
import * as types from "lib/types";

const DEVICE = "device";
const ONVIF_DEVICE_BASE_PATH = `actions/onvif/${DEVICE}`;

// CAPABILITIES OPERATIONS --------------------------------------------------------------
// //////////////////////////////////////////////////////////////////////////////////////

// Get Device Capabilities
const CAPABILITIES = "capabilities";
async function getDeviceCapabilities(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${CAPABILITIES}`,
  );
  return response.data;
}

export function useGetDeviceCapabilities(cameraIdentifier: string) {
  return useQuery<
    onvif_types.ServiceCapabilitiesResponse,
    types.APIErrorResponse
  >({
    queryKey: [DEVICE, CAPABILITIES, cameraIdentifier],
    queryFn: () => getDeviceCapabilities(cameraIdentifier),
    enabled: !!cameraIdentifier,
  });
}

// Get Device Services
const SERVICES = "services";
async function getDeviceServices(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${SERVICES}`,
  );
  return response.data;
}

export function useGetDeviceServices(cameraIdentifier: string) {
  return useQuery<onvif_types.DeviceServicesResponse, types.APIErrorResponse>({
    queryKey: [DEVICE, SERVICES, cameraIdentifier],
    queryFn: () => getDeviceServices(cameraIdentifier),
    enabled: !!cameraIdentifier,
  });
}

// SYSTEM OPERATIONS --------------------------------------------------------------------
// //////////////////////////////////////////////////////////////////////////////////////

// Get Device Information
const INFORMATION = "information";
async function getDeviceInformation(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${INFORMATION}`,
  );
  return response.data;
}

export function useGetDeviceInformation(cameraIdentifier: string) {
  return useQuery<
    onvif_types.DeviceInformationResponse,
    types.APIErrorResponse
  >({
    queryKey: [DEVICE, INFORMATION, cameraIdentifier],
    queryFn: () => getDeviceInformation(cameraIdentifier),
    enabled: !!cameraIdentifier,
  });
}

// Get Device Scopes
const SCOPES = "scopes";
async function getDeviceScopes(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${SCOPES}`,
  );
  return response.data;
}

export function useGetDeviceScopes(
  cameraIdentifier: string,
  enabled?: boolean,
) {
  return useQuery<onvif_types.DeviceScopesResponse, types.APIErrorResponse>({
    queryKey: [DEVICE, SCOPES, cameraIdentifier],
    queryFn: () => getDeviceScopes(cameraIdentifier),
    enabled: !!cameraIdentifier && (enabled ?? true),
  });
}

// Set Device Scopes
const SET_SCOPES = "set_scopes";
async function setDeviceScopes(cameraIdentifier: string, scopes: string[]) {
  const response = await viseronAPI.put(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${SET_SCOPES}`,
    { scopes },
  );
  return response.data;
}

export function useSetDeviceScopes(cameraIdentifier: string) {
  const queryClient = useQueryClient();

  return useMutation<
    onvif_types.DeviceScopesResponse,
    types.APIErrorResponse,
    string[]
  >({
    mutationFn: (scopes) => setDeviceScopes(cameraIdentifier, scopes),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [DEVICE, SCOPES, cameraIdentifier],
      });
    },
  });
}

// Add Device Scopes
const ADD_SCOPES = "add_scopes";
async function addDeviceScopes(cameraIdentifier: string, scopes: string[]) {
  const response = await viseronAPI.post(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${ADD_SCOPES}`,
    { scopes },
  );
  return response.data;
}

export function useAddDeviceScopes(cameraIdentifier: string) {
  const queryClient = useQueryClient();

  return useMutation<
    onvif_types.DeviceScopesResponse,
    types.APIErrorResponse,
    string[]
  >({
    mutationFn: (scopes) => addDeviceScopes(cameraIdentifier, scopes),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [DEVICE, SCOPES, cameraIdentifier],
      });
    },
  });
}

// Remove Device Scopes
const REMOVE_SCOPES = "remove_scopes";
async function removeDeviceScopes(cameraIdentifier: string, scopes: string) {
  const response = await viseronAPI.delete(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${REMOVE_SCOPES}?scopes=${scopes}`,
  );
  return response.data;
}

export function useRemoveDeviceScopes(cameraIdentifier: string) {
  const queryClient = useQueryClient();

  return useMutation<
    onvif_types.DeviceScopesResponse,
    types.APIErrorResponse,
    string
  >({
    mutationFn: (scopes) => removeDeviceScopes(cameraIdentifier, scopes),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [DEVICE, SCOPES, cameraIdentifier],
      });
    },
  });
}

// DATE & TIME OPERATIONS ---------------------------------------------------------------
// //////////////////////////////////////////////////////////////////////////////////////

// Get Device System Date and Time
const SYSTEM_DATE = "system_date";
async function getDeviceSystemDateAndTime(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${SYSTEM_DATE}`,
  );
  return response.data;
}

export function useGetDeviceSystemDateAndTime(cameraIdentifier: string) {
  return useQuery<
    onvif_types.DeviceSystemDateAndTimeResponse,
    types.APIErrorResponse
  >({
    queryKey: [DEVICE, SYSTEM_DATE, cameraIdentifier],
    queryFn: () => getDeviceSystemDateAndTime(cameraIdentifier),
    enabled: !!cameraIdentifier,
  });
}

// Set Device System Date and Time
const SET_SYSTEM_DATE = "set_system_date";
async function setDeviceSystemDateAndTime(
  cameraIdentifier: string,
  params: onvif_types.DeviceSystemDateAndTimeParams,
) {
  const response = await viseronAPI.put(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${SET_SYSTEM_DATE}`,
    { system_date: params },
  );
  return response.data;
}

export function useSetDeviceSystemDateAndTime(cameraIdentifier: string) {
  const queryClient = useQueryClient();

  return useMutation<
    onvif_types.DeviceSystemDateAndTimeResponse,
    types.APIErrorResponse,
    onvif_types.DeviceSystemDateAndTimeParams
  >({
    mutationFn: (params) =>
      setDeviceSystemDateAndTime(cameraIdentifier, params),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [DEVICE, SYSTEM_DATE, cameraIdentifier],
      });
    },
  });
}

// SECURITY OPERATIONS ------------------------------------------------------------------
// //////////////////////////////////////////////////////////////////////////////////////

// Get Device Users
const USERS = "users";
async function getDeviceUsers(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${USERS}`,
  );
  return response.data;
}

export function useGetDeviceUsers(cameraIdentifier: string, enabled?: boolean) {
  return useQuery<onvif_types.DeviceUsersResponse, types.APIErrorResponse>({
    queryKey: [DEVICE, USERS, cameraIdentifier],
    queryFn: () => getDeviceUsers(cameraIdentifier),
    enabled: !!cameraIdentifier && (enabled ?? true),
  });
}

// Create Device Users
const CREATE_USERS = "create_users";
async function createDeviceUsers(
  cameraIdentifier: string,
  users: onvif_types.DeviceUser[],
) {
  const response = await viseronAPI.post(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${CREATE_USERS}`,
    { users },
  );
  return response.data;
}

export function useCreateDeviceUsers(cameraIdentifier: string) {
  const queryClient = useQueryClient();

  return useMutation<
    onvif_types.DeviceUsersResponse,
    types.APIErrorResponse,
    onvif_types.DeviceUser[]
  >({
    mutationFn: (users) => createDeviceUsers(cameraIdentifier, users),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [DEVICE, USERS, cameraIdentifier],
      });
    },
  });
}

// Delete Device Users
const DELETE_USERS = "delete_users";
const USERNAME = "username";
async function deleteDeviceUsers(cameraIdentifier: string, username: string) {
  const response = await viseronAPI.delete(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${DELETE_USERS}?${USERNAME}=${username}`,
  );
  return response.data;
}

export function useDeleteDeviceUsers(cameraIdentifier: string) {
  const queryClient = useQueryClient();

  return useMutation<
    onvif_types.DeviceUsersResponse,
    types.APIErrorResponse,
    string
  >({
    mutationFn: (username) => deleteDeviceUsers(cameraIdentifier, username),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [DEVICE, USERS, cameraIdentifier],
      });
    },
  });
}

// Set Device Users
const SET_USER = "set_user";
async function setDeviceUsers(
  cameraIdentifier: string,
  users: onvif_types.DeviceUser[],
) {
  const response = await viseronAPI.put(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${SET_USER}`,
    { users },
  );
  return response.data;
}

export function useSetDeviceUsers(cameraIdentifier: string) {
  const queryClient = useQueryClient();

  return useMutation<
    onvif_types.DeviceUsersResponse,
    types.APIErrorResponse,
    onvif_types.DeviceUser[]
  >({
    mutationFn: (users) => setDeviceUsers(cameraIdentifier, users),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [DEVICE, USERS, cameraIdentifier],
      });
    },
  });
}

// NETWORK OPERATIONS -------------------------------------------------------------------
// //////////////////////////////////////////////////////////////////////////////////////

// Get Device Hostname
const HOSTNAME = "hostname";
async function getDeviceHostname(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${HOSTNAME}`,
  );
  return response.data;
}

export function useGetDeviceHostname(
  cameraIdentifier: string,
  enabled?: boolean,
) {
  return useQuery<onvif_types.DeviceHostnameResponse, types.APIErrorResponse>({
    queryKey: [DEVICE, HOSTNAME, cameraIdentifier],
    queryFn: () => getDeviceHostname(cameraIdentifier),
    enabled: !!cameraIdentifier && (enabled ?? true),
  });
}

// Set Device Hostname
const SET_HOSTNAME = "set_hostname";
async function setDeviceHostname(cameraIdentifier: string, hostname: string) {
  const response = await viseronAPI.put(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${SET_HOSTNAME}`,
    { hostname },
  );
  return response.data;
}

export function useSetDeviceHostname(cameraIdentifier: string) {
  const queryClient = useQueryClient();

  return useMutation<
    onvif_types.DeviceHostnameResponse,
    types.APIErrorResponse,
    string
  >({
    mutationFn: (hostname) => setDeviceHostname(cameraIdentifier, hostname),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [DEVICE, HOSTNAME, cameraIdentifier],
      });
    },
  });
}

// Set Device Hostname From DHCP
const SET_HOSTNAME_FROM_DHCP = "set_hostname_from_dhcp";
async function setDeviceHostnameFromDHCP(
  cameraIdentifier: string,
  fromDHCP: boolean,
) {
  const response = await viseronAPI.put(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${SET_HOSTNAME_FROM_DHCP}`,
    { from_dhcp: fromDHCP },
  );
  return response.data;
}

export function useSetDeviceHostnameFromDHCP(cameraIdentifier: string) {
  const queryClient = useQueryClient();

  return useMutation<
    onvif_types.DeviceHostnameResponse,
    types.APIErrorResponse,
    boolean
  >({
    mutationFn: (fromDHCP) =>
      setDeviceHostnameFromDHCP(cameraIdentifier, fromDHCP),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [DEVICE, HOSTNAME, cameraIdentifier],
      });
    },
  });
}

// Get Device Discovery Mode
const DISCOVERY_MODE = "discovery_mode";
async function getDeviceDiscoveryMode(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${DISCOVERY_MODE}`,
  );
  return response.data;
}

export function useGetDeviceDiscoveryMode(
  cameraIdentifier: string,
  enabled?: boolean,
) {
  return useQuery<{ discovery_mode: string }, types.APIErrorResponse>({
    queryKey: [DEVICE, DISCOVERY_MODE, cameraIdentifier],
    queryFn: () => getDeviceDiscoveryMode(cameraIdentifier),
    enabled: !!cameraIdentifier && (enabled ?? true),
  });
}

// Set Device Discovery Mode
const SET_DISCOVERY_MODE = "set_discovery_mode";
async function setDeviceDiscoveryMode(
  cameraIdentifier: string,
  discoverable: boolean,
) {
  const response = await viseronAPI.put(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${SET_DISCOVERY_MODE}`,
    { discoverable },
  );
  return response.data;
}

export function useSetDeviceDiscoveryMode(cameraIdentifier: string) {
  const queryClient = useQueryClient();

  return useMutation<
    { discovery_mode: string },
    types.APIErrorResponse,
    boolean
  >({
    mutationFn: (discoverable) =>
      setDeviceDiscoveryMode(cameraIdentifier, discoverable),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [DEVICE, DISCOVERY_MODE, cameraIdentifier],
      });
    },
  });
}

// Get Device NTP
const NTP = "ntp";
async function getDeviceNTP(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${NTP}`,
  );
  return response.data;
}

export function useGetDeviceNTP(cameraIdentifier: string, enabled?: boolean) {
  return useQuery<onvif_types.DeviceNTPResponse, types.APIErrorResponse>({
    queryKey: [DEVICE, NTP, cameraIdentifier],
    queryFn: () => getDeviceNTP(cameraIdentifier),
    enabled: !!cameraIdentifier && (enabled ?? true),
  });
}

// Set Device NTP
const SET_NTP = "set_ntp";
async function setDeviceNTP(
  cameraIdentifier: string,
  params: onvif_types.DeviceNTPParams,
) {
  const response = await viseronAPI.put(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${SET_NTP}`,
    { ntp: params },
  );
  return response.data;
}

export function useSetDeviceNTP(cameraIdentifier: string) {
  const queryClient = useQueryClient();

  return useMutation<
    onvif_types.DeviceNTPResponse,
    types.APIErrorResponse,
    onvif_types.DeviceNTPParams
  >({
    mutationFn: (params) => setDeviceNTP(cameraIdentifier, params),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [DEVICE, NTP, cameraIdentifier],
      });
    },
  });
}

// Get Network Default Gateway
const NETWORK_DEFAULT_GATEWAY = "network_default_gateway";
async function getDeviceNetworkDefaultGateway(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${NETWORK_DEFAULT_GATEWAY}`,
  );
  return response.data;
}

export function useGetDeviceNetworkDefaultGateway(
  cameraIdentifier: string,
  enabled?: boolean,
) {
  return useQuery<
    onvif_types.DeviceNetworkDefaultGatewayResponse,
    types.APIErrorResponse
  >({
    queryKey: [DEVICE, NETWORK_DEFAULT_GATEWAY, cameraIdentifier],
    queryFn: () => getDeviceNetworkDefaultGateway(cameraIdentifier),
    enabled: !!cameraIdentifier && (enabled ?? true),
  });
}

// Set Network Default Gateway
const SET_NETWORK_DEFAULT_GATEWAY = "set_network_default_gateway";
async function setDeviceNetworkDefaultGateway(
  cameraIdentifier: string,
  params: onvif_types.DeviceNetworkDefaultGatewayParams,
) {
  const response = await viseronAPI.put(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${SET_NETWORK_DEFAULT_GATEWAY}`,
    { network_default_gateway: params },
  );
  return response.data;
}

export function useSetDeviceNetworkDefaultGateway(cameraIdentifier: string) {
  const queryClient = useQueryClient();

  return useMutation<
    onvif_types.DeviceNetworkDefaultGatewayResponse,
    types.APIErrorResponse,
    onvif_types.DeviceNetworkDefaultGatewayParams
  >({
    mutationFn: (params) =>
      setDeviceNetworkDefaultGateway(cameraIdentifier, params),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [DEVICE, NETWORK_DEFAULT_GATEWAY, cameraIdentifier],
      });
    },
  });
}

// Get Device Network Protocols
const NETWORK_PROTOCOLS = "network_protocols";
async function getDeviceNetworkProtocols(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${NETWORK_PROTOCOLS}`,
  );
  return response.data;
}

export function useGetDeviceNetworkProtocols(
  cameraIdentifier: string,
  enabled?: boolean,
) {
  return useQuery<
    onvif_types.DeviceNetworkProtocolsResponse,
    types.APIErrorResponse
  >({
    queryKey: [DEVICE, NETWORK_PROTOCOLS, cameraIdentifier],
    queryFn: () => getDeviceNetworkProtocols(cameraIdentifier),
    enabled: !!cameraIdentifier && (enabled ?? true),
  });
}

// Set Device Network Protocols
const SET_NETWORK_PROTOCOLS = "set_network_protocols";
async function setDeviceNetworkProtocols(
  cameraIdentifier: string,
  params: onvif_types.DeviceNetworkProtocolsParams,
) {
  const response = await viseronAPI.put(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${SET_NETWORK_PROTOCOLS}`,
    params,
  );
  return response.data;
}

export function useSetDeviceNetworkProtocols(cameraIdentifier: string) {
  const queryClient = useQueryClient();

  return useMutation<
    onvif_types.DeviceNetworkProtocolsResponse,
    types.APIErrorResponse,
    onvif_types.DeviceNetworkProtocolsParams
  >({
    mutationFn: (params) => setDeviceNetworkProtocols(cameraIdentifier, params),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [DEVICE, NETWORK_PROTOCOLS, cameraIdentifier],
      });
    },
  });
}

// Get Device Network Interfaces
const NETWORK_INTERFACES = "network_interfaces";
async function getDeviceNetworkInterfaces(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${NETWORK_INTERFACES}`,
  );
  return response.data;
}

export function useGetDeviceNetworkInterfaces(
  cameraIdentifier: string,
  enabled?: boolean,
) {
  return useQuery<
    onvif_types.DeviceNetworkInterfacesResponse,
    types.APIErrorResponse
  >({
    queryKey: [DEVICE, NETWORK_INTERFACES, cameraIdentifier],
    queryFn: () => getDeviceNetworkInterfaces(cameraIdentifier),
    enabled: !!cameraIdentifier && (enabled ?? true),
  });
}

// Set Device Network Interfaces
const SET_NETWORK_INTERFACES = "set_network_interfaces";
async function setDeviceNetworkInterfaces(
  cameraIdentifier: string,
  params: onvif_types.DeviceNetworkInterfacesParams,
) {
  const response = await viseronAPI.put(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${SET_NETWORK_INTERFACES}`,
    params,
  );
  return response.data;
}

export function useSetDeviceNetworkInterfaces(cameraIdentifier: string) {
  const queryClient = useQueryClient();

  return useMutation<
    types.APISuccessResponse,
    types.APIErrorResponse,
    onvif_types.DeviceNetworkInterfaceSetParams
  >({
    mutationFn: (params) =>
      setDeviceNetworkInterfaces(cameraIdentifier, {
        network_interfaces: params,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [DEVICE, NETWORK_INTERFACES, cameraIdentifier],
      });
    },
  });
}

// Get Device DNS
const DNS = "dns";
async function getDeviceDNS(cameraIdentifier: string) {
  const response = await viseronAPI.get(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${DNS}`,
  );
  return response.data;
}

export function useGetDeviceDNS(cameraIdentifier: string, enabled?: boolean) {
  return useQuery<onvif_types.DeviceDNSResponse, types.APIErrorResponse>({
    queryKey: [DEVICE, DNS, cameraIdentifier],
    queryFn: () => getDeviceDNS(cameraIdentifier),
    enabled: !!cameraIdentifier && (enabled ?? true),
  });
}

// Set Device DNS
const SET_DNS = "set_dns";
async function setDeviceDNS(
  cameraIdentifier: string,
  params: onvif_types.DeviceDNSParams,
) {
  const response = await viseronAPI.put(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${SET_DNS}`,
    { dns: params },
  );
  return response.data;
}

export function useSetDeviceDNS(cameraIdentifier: string) {
  const queryClient = useQueryClient();

  return useMutation<
    onvif_types.DeviceDNSResponse,
    types.APIErrorResponse,
    onvif_types.DeviceDNSParams
  >({
    mutationFn: (params) => setDeviceDNS(cameraIdentifier, params),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [DEVICE, DNS, cameraIdentifier],
      });
    },
  });
}

// ACTION OPERATIONS --------------------------------------------------------------------
// //////////////////////////////////////////////////////////////////////////////////////

// Device Reboot
const REBOOT = "reboot";
async function deviceReboot(cameraIdentifier: string) {
  const response = await viseronAPI.post(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${REBOOT}`,
    {},
  );
  return response.data;
}

export function useDeviceReboot(cameraIdentifier: string) {
  return useMutation<void, types.APIErrorResponse>({
    mutationFn: () => deviceReboot(cameraIdentifier),
  });
}

// Device Factory Reset
const FACTORY_RESET = "factory_reset";
async function deviceFactoryReset(
  cameraIdentifier: string,
  level: string = "Soft",
) {
  const response = await viseronAPI.post(
    `${ONVIF_DEVICE_BASE_PATH}/${cameraIdentifier}/${FACTORY_RESET}`,
    { level },
  );
  return response.data;
}

export function useDeviceFactoryReset(cameraIdentifier: string) {
  return useMutation<void, types.APIErrorResponse, string>({
    mutationFn: (level) => deviceFactoryReset(cameraIdentifier, level),
  });
}
