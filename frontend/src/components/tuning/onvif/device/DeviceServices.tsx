import {
  Activity,
  Api,
  Camera,
  Chip as ChipIcon,
  EventSchedule,
  Help,
  Image,
  Move,
  Recording,
  Repeat,
  Search,
  Video,
} from "@carbon/icons-react";
import { Box, Chip, Stack, Tooltip, Typography } from "@mui/material";

import { useGetDeviceServices } from "lib/api/actions/onvif/device";

import { QueryWrapper } from "../../config/QueryWrapper";

interface DeviceServicesProps {
  cameraIdentifier: string;
}

// Helper to get icon for service
const getServiceIcon = (serviceName: string) => {
  const lowerName = serviceName.toLowerCase();

  if (lowerName.includes("media")) return <Video size={16} />;
  if (lowerName.includes("deviceio")) return <ChipIcon size={16} />;
  if (lowerName.includes("device")) return <Camera size={16} />;
  if (lowerName === "ptz") return <Move size={16} />;
  if (lowerName.includes("imaging")) return <Image size={16} />;
  if (lowerName.includes("event")) return <EventSchedule size={16} />;
  if (lowerName.includes("analytics")) return <Activity size={16} />;
  if (lowerName.includes("recording")) return <Recording size={16} />;
  if (lowerName.includes("search")) return <Search size={16} />;
  if (lowerName.includes("replay")) return <Repeat size={16} />;
  if (lowerName.includes("receiver")) return <Camera size={16} />;

  return <Api size={16} />;
};

export function DeviceServices({ cameraIdentifier }: DeviceServicesProps) {
  const TITLE = "Available Services";
  const DESC = "READ-ONLY: List of ONVIF services supported by the device.";

  // ONVIF API hook
  const { data, isLoading, isError, error } =
    useGetDeviceServices(cameraIdentifier);

  const services = data?.services;

  // Helper to extract service name from namespace
  const getServiceName = (namespace: string): string => {
    const match = namespace.match(/\/ver(\d+)\/(\w+)\//);
    if (match) {
      const version = parseInt(match[1], 10);
      const rawName = match[2];

      // Special case: PTZ should be uppercase
      if (rawName.toLowerCase() === "ptz") {
        return "PTZ";
      }

      // Capitalize first letter, preserve rest (e.g., deviceIO -> DeviceIO)
      const serviceName = rawName.charAt(0).toUpperCase() + rawName.slice(1);

      // ver20 means version 2 only for media service (e.g., Media2)
      if (version >= 20 && rawName.toLowerCase() === "media") {
        return `${serviceName}2`;
      }

      return serviceName;
    }
    return namespace;
  };

  return (
    <QueryWrapper
      isLoading={isLoading}
      isError={isError}
      errorMessage={error?.message || "Failed to load device services"}
      isEmpty={!services || services.length === 0}
      title={TITLE}
    >
      <Box>
        <Box
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          mb={1}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Typography variant="subtitle2">{TITLE}</Typography>
            <Tooltip title={DESC} arrow placement="top">
              <Help size={16} />
            </Tooltip>
          </Box>
        </Box>

        {/* Services List */}
        <Stack direction="row" flexWrap="wrap" gap={0.7}>
          {services?.map(
            (service: {
              Namespace: string;
              Version?: { Major: number; Minor: number };
            }) => {
              const serviceName = getServiceName(service.Namespace);
              return (
                <Tooltip
                  key={service.Namespace}
                  title={`v${service.Version?.Major || 0}.${service.Version?.Minor || 0}`}
                  placement="top"
                  arrow
                >
                  <Chip
                    sx={{
                      pl: 0.5,
                    }}
                    icon={getServiceIcon(serviceName)}
                    label={serviceName}
                    size="medium"
                    variant="filled"
                    color="default"
                  />
                </Tooltip>
              );
            },
          )}
        </Stack>
      </Box>
    </QueryWrapper>
  );
}
