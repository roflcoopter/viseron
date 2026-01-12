import { NetworkTimeProtocol } from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";

import { useCameraUptime } from "hooks/UseCameraUptime";

interface CameraUptimeProps {
  cameraIdentifier: string;
  isConnected: boolean;
  compact?: boolean;
}

export function CameraUptime({
  cameraIdentifier,
  isConnected,
  compact = false,
}: CameraUptimeProps) {
  const theme = useTheme();
  const { uptime } = useCameraUptime(cameraIdentifier, isConnected);

  // Force "Offline" display when disconnected regardless of uptime value
  const displayText = isConnected ? uptime : "Offline";
  const displayUptimeText = isConnected
    ? `Uptime: ${uptime}`
    : "Camera Offline";

  if (compact) {
    return (
      <Chip
        icon={
          <NetworkTimeProtocol
            style={{
              width: "clamp(18px, 3vw, 20px)",
              height: "clamp(18px, 3vw, 20px)",
            }}
          />
        }
        label={displayText}
        size="small"
        color={isConnected ? "default" : "error"}
        sx={{
          fontSize: "0.75rem",
          height: 30,
          borderRadius: 1.2,
          px: 0.5,
          py: 1,
        }}
      />
    );
  }

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 1,
        py: 1,
        px: 2,
        backgroundColor: isConnected
          ? theme.palette.success.light
          : theme.palette.error.light,
        color: isConnected
          ? theme.palette.success.contrastText
          : theme.palette.error.contrastText,
        borderRadius: 0,
        mx: 2,
        mb: 1,
      }}
    >
      <NetworkTimeProtocol size={20} />
      <Typography variant="body2" fontWeight="medium">
        {displayUptimeText}
      </Typography>
    </Box>
  );
}
