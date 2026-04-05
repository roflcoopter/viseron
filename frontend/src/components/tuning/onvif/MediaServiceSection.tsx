import { Box } from "@mui/material";

import { MediaProfiles } from "./media";

interface MediaServiceSectionProps {
  cameraIdentifier: string;
  isOnvifAutoConfig?: boolean;
}

export function MediaServiceSection({
  cameraIdentifier,
  isOnvifAutoConfig,
}: MediaServiceSectionProps) {
  return (
    <Box
      display="flex"
      gap={2.5}
      flexDirection="column"
      mb={isOnvifAutoConfig ? 0 : 2.5}
      mt={0.5}
    >
      <MediaProfiles cameraIdentifier={cameraIdentifier} />
    </Box>
  );
}
