import { Box } from "@mui/material";

import { useGetPtzNodes } from "lib/api/actions/onvif/ptz";

import { PTZMovements, PTZPositions } from "./ptz";

interface PTZServiceSectionProps {
  cameraIdentifier: string;
  isOnvifAutoConfig?: boolean;
}

export function PTZServiceSection({
  cameraIdentifier,
  isOnvifAutoConfig,
}: PTZServiceSectionProps) {
  const {
    data: ptzNodes,
    isLoading,
    isError,
    error,
  } = useGetPtzNodes(cameraIdentifier);

  return (
    <Box
      display="flex"
      gap={2.5}
      flexDirection="column"
      mb={isOnvifAutoConfig ? 0 : 2.5}
      mt={0.5}
    >
      <PTZMovements
        cameraIdentifier={cameraIdentifier}
        ptzNodes={ptzNodes}
        isLoading={isLoading}
        isError={isError}
        error={error}
      />
      <PTZPositions
        cameraIdentifier={cameraIdentifier}
        ptzNodes={ptzNodes}
        isLoading={isLoading}
        isError={isError}
        error={error}
      />
    </Box>
  );
}
