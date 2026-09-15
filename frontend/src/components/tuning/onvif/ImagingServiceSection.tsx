import { Box } from "@mui/material";

import {
  useGetImagingCapabilities,
  useGetImagingMoveOptions,
} from "lib/api/actions/onvif/imaging";

import { ImagingMove, ImagingPresets, ImagingSettings } from "./imaging";

interface ImagingServiceSectionProps {
  cameraIdentifier: string;
  isOnvifAutoConfig?: boolean;
  onSettingsApplied?: () => void;
}

export function ImagingServiceSection({
  cameraIdentifier,
  isOnvifAutoConfig,
  onSettingsApplied,
}: ImagingServiceSectionProps) {
  const { data: imagingCapababilities } =
    useGetImagingCapabilities(cameraIdentifier);
  const { data: imagingMoveOptions } =
    useGetImagingMoveOptions(cameraIdentifier);

  const hasPresets = imagingCapababilities?.capabilities?.Presets;
  const hasMoveOptions =
    imagingMoveOptions?.move_options?.Absolute ||
    imagingMoveOptions?.move_options?.Relative ||
    imagingMoveOptions?.move_options?.Continuous;

  return (
    <Box
      display="flex"
      gap={2.5}
      flexDirection="column"
      mb={isOnvifAutoConfig ? 0 : 2.5}
      mt={0.5}
    >
      <ImagingSettings
        cameraIdentifier={cameraIdentifier}
        onSettingsApplied={onSettingsApplied}
      />
      {hasPresets && (
        <ImagingPresets
          cameraIdentifier={cameraIdentifier}
          onSettingsApplied={onSettingsApplied}
        />
      )}
      {hasMoveOptions && (
        <ImagingMove
          cameraIdentifier={cameraIdentifier}
          onSettingsApplied={onSettingsApplied}
          imagingMoveOptions={imagingMoveOptions?.move_options}
        />
      )}
    </Box>
  );
}
