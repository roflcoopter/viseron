import { AddAlt, Help, PaintBrush, SprayPaint } from "@carbon/icons-react";
import {
  Box,
  Button,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Tooltip,
  Typography,
} from "@mui/material";
import { MouseEvent, useState } from "react";

import { useToast } from "hooks/UseToast";
import {
  useGetImagingPresets,
  useSetCurrentImagingPreset,
} from "lib/api/actions/onvif/imaging";

import { QueryWrapper } from "../../config/QueryWrapper";

interface ImagingPresetsProps {
  cameraIdentifier: string;
  onSettingsApplied?: () => void;
}

export function ImagingPresets({
  cameraIdentifier,
  onSettingsApplied,
}: ImagingPresetsProps) {
  const toast = useToast();
  const {
    data: imagingPresets,
    isLoading,
    isError,
    error,
  } = useGetImagingPresets(cameraIdentifier);
  const setPresetMutation = useSetCurrentImagingPreset(cameraIdentifier);

  // Context menu state
  const [contextMenu, setContextMenu] = useState<{
    mouseX: number;
    mouseY: number;
    token: string;
  } | null>(null);

  const handleContextMenu = (
    event: MouseEvent<HTMLButtonElement>,
    token: string,
  ) => {
    event.preventDefault();
    setContextMenu({
      mouseX: event.clientX,
      mouseY: event.clientY,
      token,
    });
  };

  const handleApplyPreset = (token: string) => {
    setPresetMutation.mutate(token, {
      onSuccess: () => {
        toast.success("Imaging preset applied successfully.");
        onSettingsApplied?.();
      },
      onError: (err) => {
        toast.error(err?.message || "Failed to apply imaging preset.");
      },
    });
  };

  const handleContextMenuClose = () => {
    setContextMenu(null);
  };
  const presets = imagingPresets?.presets;

  return (
    <QueryWrapper
      isLoading={isLoading}
      isError={isError}
      errorMessage={error?.message || "Failed to load imaging presets."}
      isEmpty={presets === undefined || presets.length === 0}
      showEmptyAlert
      title="Imaging Presets"
    >
      <Box>
        <Box
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          mb={1}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Typography variant="subtitle2">Imaging Presets</Typography>
            <Tooltip
              title="Manage ONVIF imaging presets."
              arrow
              placement="top"
            >
              <Help size={16} />
            </Tooltip>
          </Box>
          <Button size="small" startIcon={<AddAlt size={16} />}>
            Add
          </Button>
        </Box>
        {presets && presets.length > 0 ? (
          <Box display="flex" flexDirection="column" gap={1}>
            {presets.map((preset) => (
              <Button
                key={preset.Name}
                variant="outlined"
                fullWidth
                onContextMenu={(e) => handleContextMenu(e, preset.Name)}
                color="info"
                sx={{
                  p: 1.5,
                  display: "flex",
                  justifyContent: "flex-start",
                  textTransform: "none",
                }}
              >
                <PaintBrush style={{ marginRight: 8, flexShrink: 0 }} />
                <Typography
                  variant="body2"
                  sx={{
                    fontWeight: 500,
                    flexGrow: 1,
                    textAlign: "left",
                  }}
                >
                  {preset.Name}
                </Typography>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ flexShrink: 0 }}
                >
                  {preset.type}
                </Typography>
              </Button>
            ))}
          </Box>
        ) : (
          <Typography
            variant="caption"
            color="text.secondary"
            display="block"
            sx={{ ml: 1 }}
          >
            No presets configured
          </Typography>
        )}

        {/* Context Menu */}
        <Menu
          open={contextMenu !== null}
          onClose={handleContextMenuClose}
          anchorReference="anchorPosition"
          anchorPosition={
            contextMenu !== null
              ? { top: contextMenu.mouseY, left: contextMenu.mouseX }
              : undefined
          }
        >
          <MenuItem
            onClick={() => {
              if (contextMenu) {
                handleApplyPreset(contextMenu.token);
              }
              handleContextMenuClose();
            }}
            sx={{ color: "primary.main" }}
          >
            <ListItemIcon sx={{ color: "primary.main" }}>
              <SprayPaint />
            </ListItemIcon>
            <ListItemText>Apply This Preset</ListItemText>
          </MenuItem>
        </Menu>
      </Box>
    </QueryWrapper>
  );
}
