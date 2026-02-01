import { Box } from "@mui/material";

import { PTZMovements } from "./ptz";

interface PTZServiceSectionProps {
  cameraIdentifier: string;
  isOnvifAutoConfig?: boolean;
}

export function PTZServiceSection({
  cameraIdentifier,
  isOnvifAutoConfig,
}: PTZServiceSectionProps) {
  return (
    <Box
      display="flex"
      gap={2.5}
      flexDirection="column"
      mb={isOnvifAutoConfig ? 0 : 2.5}
      mt={0.5}
    >
      <PTZMovements cameraIdentifier={cameraIdentifier} />
    </Box>
  );
}
