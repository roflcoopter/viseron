import { Box } from "@mui/material";

import { useGetMediaCapabilities } from "lib/api/actions/onvif/media";

import { MediaProfiles, MediaUri } from "./media";

interface MediaServiceSectionProps {
  cameraIdentifier: string;
  isOnvifAutoConfig?: boolean;
}

export function MediaServiceSection({
  cameraIdentifier,
  isOnvifAutoConfig,
}: MediaServiceSectionProps) {
  const { data: mediaCapabilities } = useGetMediaCapabilities(cameraIdentifier);

  return (
    <Box
      display="flex"
      gap={2.5}
      flexDirection="column"
      mb={isOnvifAutoConfig ? 0 : 2.5}
      mt={0.5}
    >
      <MediaProfiles
        cameraIdentifier={cameraIdentifier}
        mediaCapabilities={mediaCapabilities?.capabilities}
      />
      <MediaUri
        cameraIdentifier={cameraIdentifier}
        mediaCapabilities={mediaCapabilities?.capabilities}
      />
    </Box>
  );
}
