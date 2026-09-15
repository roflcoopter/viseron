import { Reset, SettingsServices } from "@carbon/icons-react";
import { Box, Button, Typography, useTheme } from "@mui/material";

interface ConfigPanelHeaderProps {
  isConfigModified: boolean;
  isDrawingMode: boolean;
  isSaving: boolean;
  onRevertConfig: () => void;
  currentDomainName: string;
  componentName?: string;
  isOnvifAutoConfig?: boolean;
}

export function ConfigPanelHeader({
  isConfigModified,
  isDrawingMode,
  isSaving,
  onRevertConfig,
  currentDomainName,
  componentName,
  isOnvifAutoConfig,
}: ConfigPanelHeaderProps) {
  const theme = useTheme();

  // Hide reset button for ONVIF components (except client) when auto_config is true
  const shouldShowResetButton = !(
    currentDomainName === "onvif" &&
    componentName !== "client" &&
    isOnvifAutoConfig
  );

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        color:
          theme.palette.mode === "dark"
            ? theme.palette.primary[300]
            : theme.palette.primary.main,
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center" }}>
        <SettingsServices size={20} style={{ marginRight: 8 }} />
        <Typography variant="h6">Tuning Config</Typography>
      </Box>
      {shouldShowResetButton && (
        <Button
          size="small"
          startIcon={<Reset size={16} />}
          onClick={onRevertConfig}
          disabled={!isConfigModified || isDrawingMode || isSaving}
          color="warning"
        >
          RESET
        </Button>
      )}
    </Box>
  );
}
