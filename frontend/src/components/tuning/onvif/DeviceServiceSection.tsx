import { Box } from "@mui/material";

import { useGetDeviceCapabilities } from "lib/api/actions/onvif/device";

import {
  DeviceActions,
  DeviceDNS,
  DeviceInformation,
  DeviceNTP,
  DeviceNetworkInterfaces,
  DeviceNetworkProtocols,
  DeviceNetworkSettings,
  DeviceScopes,
  DeviceServices,
  DeviceSystemDateAndTime,
  DeviceUsers,
} from "./device";

interface DeviceServiceSectionProps {
  cameraIdentifier: string;
  isOnvifAutoConfig?: boolean;
}

export function DeviceServiceSection({
  cameraIdentifier,
  isOnvifAutoConfig,
}: DeviceServiceSectionProps) {
  const {
    data: deviceCapabilities,
    isError,
    isLoading,
  } = useGetDeviceCapabilities(cameraIdentifier);

  return (
    <Box
      display="flex"
      gap={2.5}
      flexDirection="column"
      mb={isOnvifAutoConfig ? 0 : 2.5}
      mt={0.5}
    >
      <DeviceInformation cameraIdentifier={cameraIdentifier} />
      <DeviceServices cameraIdentifier={cameraIdentifier} />
      <DeviceScopes
        cameraIdentifier={cameraIdentifier}
        deviceCapabilities={deviceCapabilities?.capabilities}
      />
      <DeviceUsers
        cameraIdentifier={cameraIdentifier}
        deviceCapabilities={deviceCapabilities?.capabilities}
      />
      <DeviceSystemDateAndTime cameraIdentifier={cameraIdentifier} />
      <DeviceNTP
        cameraIdentifier={cameraIdentifier}
        deviceCapabilities={deviceCapabilities?.capabilities}
      />
      <DeviceNetworkSettings
        cameraIdentifier={cameraIdentifier}
        deviceCapabilities={deviceCapabilities?.capabilities}
      />
      <DeviceNetworkProtocols
        cameraIdentifier={cameraIdentifier}
        deviceCapabilities={deviceCapabilities?.capabilities}
      />
      <DeviceNetworkInterfaces
        cameraIdentifier={cameraIdentifier}
        deviceCapabilities={deviceCapabilities?.capabilities}
      />
      <DeviceDNS
        cameraIdentifier={cameraIdentifier}
        deviceCapabilities={deviceCapabilities?.capabilities}
      />
      <DeviceActions
        cameraIdentifier={cameraIdentifier}
        isLoading={isLoading}
        isAvailable={!isError}
      />
    </Box>
  );
}
