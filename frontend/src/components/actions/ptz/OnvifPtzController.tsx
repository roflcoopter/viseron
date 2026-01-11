import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Close,
  DataCollection,
  Flag,
  Home,
  ImageSearchAlt,
  Move,
  StopFilledAlt,
  TrashCan,
  ZAxis,
  ZoomIn,
  ZoomOut,
} from "@carbon/icons-react";
import {
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Drawer,
  FormControl,
  FormControlLabel,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Slider,
  Switch,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import Stack from "@mui/material/Stack";
import { useTheme } from "@mui/material/styles";
import { useEffect, useState } from "react";

import { CustomFab } from "components/player/CustomControls";
import {
  useGetPtzConfig,
  useGetPtzNodes,
  useGetPtzPresets,
} from "lib/api/actions/onvif/ptz";

import { useOnvifPtzHandlers } from "./useOnvifPtzHandlers";

interface OnvifPtzControllerProps {
  cameraIdentifier: string;
}

export function OnvifPtzController({
  cameraIdentifier,
}: OnvifPtzControllerProps) {
  const theme = useTheme();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [presetsDialogOpen, setPresetsDialogOpen] = useState(false);
  const [savePresetDialogOpen, setSavePresetDialogOpen] = useState(false);
  const [setHomeDialogOpen, setSetHomeDialogOpen] = useState(false);
  const [removePresetDialogOpen, setRemovePresetDialogOpen] = useState(false);
  const [newPresetName, setNewPresetName] = useState("");
  const [selectedPresetToken, setSelectedPresetToken] = useState<string>("");
  const [selectedPresetName, setSelectedPresetName] = useState<string>("");
  const [moveSpeed, setMoveSpeed] = useState(0.5);

  const { data: nodesData } = useGetPtzNodes(cameraIdentifier);

  // Extract capabilities from nodes
  const ptzNode = nodesData?.nodes?.[0];
  const supportsPresets =
    ptzNode?.MaximumNumberOfPresets && ptzNode.MaximumNumberOfPresets > 0;
  const supportsHome = ptzNode?.HomeSupported === true;
  const supportsAbsoluteMove =
    !!ptzNode?.SupportedPTZSpaces?.AbsolutePanTiltPositionSpace?.length; // To determine whether Absolute Move is supported by the device for user-defined PTZ presets
  const supportsZoom =
    !!ptzNode?.SupportedPTZSpaces?.ContinuousZoomVelocitySpace?.length; // To determine whether zoom in Continuous Move is supported

  // Get velocity ranges from nodes (Continuous Move)
  const panTiltSpace =
    ptzNode?.SupportedPTZSpaces?.ContinuousPanTiltVelocitySpace?.[0];
  const zoomSpace =
    ptzNode?.SupportedPTZSpaces?.ContinuousZoomVelocitySpace?.[0];

  const panTiltMinMax = {
    xMin: panTiltSpace?.XRange?.Min ?? -1.0,
    xMax: panTiltSpace?.XRange?.Max ?? 1.0,
    yMin: panTiltSpace?.YRange?.Min ?? -1.0,
    yMax: panTiltSpace?.YRange?.Max ?? 1.0,
  };

  const zoomMinMax = {
    min: zoomSpace?.XRange?.Min ?? -1.0,
    max: zoomSpace?.XRange?.Max ?? 1.0,
  };

  // Get speed ranges from nodes
  const panTiltSpeedSpace = ptzNode?.SupportedPTZSpaces?.PanTiltSpeedSpace?.[0];
  const zoomSpeedSpace = ptzNode?.SupportedPTZSpaces?.ZoomSpeedSpace?.[0];

  const speedMinMax = {
    panTiltMin: panTiltSpeedSpace?.XRange?.Min ?? 0.0,
    panTiltMax: panTiltSpeedSpace?.XRange?.Max ?? 1.0,
    zoomMin: zoomSpeedSpace?.XRange?.Min ?? 0.0,
    zoomMax: zoomSpeedSpace?.XRange?.Max ?? 1.0,
  };

  const { data: presetsData, refetch: refetchPresets } = useGetPtzPresets(
    cameraIdentifier,
    "onvif",
  );

  const { data: configData } = useGetPtzConfig(cameraIdentifier);

  const [reversePan, setReversePan] = useState<boolean>(
    typeof configData?.user_config?.reverse_pan === "boolean"
      ? configData.user_config.reverse_pan
      : false,
  );
  const [reverseTilt, setReverseTilt] = useState<boolean>(
    typeof configData?.user_config?.reverse_tilt === "boolean"
      ? configData.user_config.reverse_tilt
      : false,
  );

  useEffect(() => {
    const pan = configData?.user_config?.reverse_pan;
    if (typeof pan === "boolean" && pan !== reversePan) {
      setReversePan(pan);
    }
    const tilt = configData?.user_config?.reverse_tilt;
    if (typeof tilt === "boolean" && tilt !== reverseTilt) {
      setReverseTilt(tilt);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    configData?.user_config?.reverse_pan,
    configData?.user_config?.reverse_tilt,
  ]);

  // Combine user-defined presets with ONVIF presets if auto-config is disabled
  const userPresets = supportsAbsoluteMove
    ? (configData?.user_config?.presets || []).map((preset) => ({
        Name: preset.name,
        type: "user_defined",
        token: preset.name,
        move_on_startup: preset.on_startup || false,
        PTZPosition: {
          PanTilt: { x: preset.pan, y: preset.tilt },
          Zoom:
            typeof preset.zoom === "number" ? { x: preset.zoom } : undefined,
        },
      }))
    : [];
  const onvifPresets = presetsData?.presets || [];
  const allPresets = [...userPresets, ...onvifPresets];

  const isAutoConfig = !configData;

  // Use ONVIF PTZ handlers hook
  const {
    handleMoveStart,
    handleStop,
    handleGoHome,
    handleSetHome,
    handleGotoPreset,
    handleSavePreset,
    handleRemovePreset,
    handleAbsoluteMove,
    mutations,
  } = useOnvifPtzHandlers({
    cameraIdentifier,
    isAutoConfig,
    moveSpeed,
    reversePan,
    reverseTilt,
    ranges: { panTiltMinMax, zoomMinMax, speedMinMax },
    refetchPresets,
    setPresetsDialogOpen,
    setSetHomeDialogOpen,
    setNewPresetName,
    setSavePresetDialogOpen,
    presetsData,
    configData,
  });

  return (
    <>
      {/* PTZ FAB Button */}
      <CustomFab onClick={() => setDrawerOpen(true)} title="PTZ Controls">
        <Move />
      </CustomFab>

      {/* PTZ Controls Drawer */}
      <Drawer
        anchor="right"
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false);
          handleStop(); // Stop all movement when closing drawer
        }}
        slotProps={{
          paper: {
            sx: {
              width: { xs: 310, md: 300 },
              p: 2,
              overflowX: "hidden",
              overflowY: "auto",
              zIndex: 9004,
            },
          },
        }}
        sx={{
          "& .MuiDrawer-paper": {
            borderTop: "none !important",
            borderBottom: "none !important",
            borderRight: "none !important",
          },
          zIndex: 9004,
        }}
      >
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            mb: 2,
            color:
              theme.palette.mode === "dark"
                ? theme.palette.primary[300]
                : theme.palette.primary.main,
          }}
        >
          <Stack direction="row" alignItems="center" spacing={1}>
            <Move size={24} />
            <Typography variant="h6">PTZ Controls</Typography>
          </Stack>
          <IconButton
            size="small"
            onClick={() => {
              setDrawerOpen(false);
              handleStop();
            }}
          >
            <Close size={20} />
          </IconButton>
        </Box>

        {/* Directional Controls */}
        <Box
          sx={{
            p: 1,
            mb: 2,
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gridTemplateRows: "repeat(3, 1fr)",
            gap: 0.5,
            aspectRatio: "1",
          }}
        >
          {/* Top Row */}
          <Box />
          <Tooltip
            title="Tilt Up"
            PopperProps={{
              style: { zIndex: 9005 },
            }}
          >
            <IconButton
              onMouseDown={() => handleMoveStart(0, 1)}
              onMouseUp={handleStop}
              onTouchStart={() => handleMoveStart(0, 1)}
              onTouchEnd={handleStop}
              sx={{ bgcolor: "action.hover" }}
            >
              <ArrowUp size={24} />
            </IconButton>
          </Tooltip>
          <Tooltip
            title="Zoom In"
            PopperProps={{
              style: { zIndex: 9005 },
            }}
          >
            <IconButton
              onMouseDown={() => handleMoveStart(0, 0, 0.1)}
              onMouseUp={handleStop}
              onTouchStart={() => handleMoveStart(0, 0, 0.1)}
              onTouchEnd={handleStop}
              sx={{ bgcolor: "action.hover" }}
              disabled={!supportsZoom}
            >
              <ZoomIn size={24} />
            </IconButton>
          </Tooltip>

          {/* Middle Row */}
          <Tooltip
            title="Pan Left"
            PopperProps={{
              style: { zIndex: 9005 },
            }}
          >
            <IconButton
              onMouseDown={() => handleMoveStart(-1, 0)}
              onMouseUp={handleStop}
              onTouchStart={() => handleMoveStart(-1, 0)}
              onTouchEnd={handleStop}
              sx={{ bgcolor: "action.hover" }}
            >
              <ArrowLeft size={24} />
            </IconButton>
          </Tooltip>
          <Tooltip
            title="Stop"
            PopperProps={{
              style: { zIndex: 9005 },
            }}
          >
            <IconButton onClick={handleStop} sx={{ bgcolor: "error.dark" }}>
              <StopFilledAlt size={24} />
            </IconButton>
          </Tooltip>
          <Tooltip
            title="Pan Right"
            PopperProps={{
              style: { zIndex: 9005 },
            }}
          >
            <IconButton
              onMouseDown={() => handleMoveStart(1, 0)}
              onMouseUp={handleStop}
              onTouchStart={() => handleMoveStart(1, 0)}
              onTouchEnd={handleStop}
              sx={{ bgcolor: "action.hover" }}
            >
              <ArrowRight size={24} />
            </IconButton>
          </Tooltip>

          {/* Bottom Row */}
          <Box />
          <Tooltip
            title="Tilt Down"
            PopperProps={{
              style: { zIndex: 9005 },
            }}
          >
            <IconButton
              onMouseDown={() => handleMoveStart(0, -1)}
              onMouseUp={handleStop}
              onTouchStart={() => handleMoveStart(0, -1)}
              onTouchEnd={handleStop}
              sx={{ bgcolor: "action.hover" }}
            >
              <ArrowDown size={24} />
            </IconButton>
          </Tooltip>
          <Tooltip
            title="Zoom Out"
            PopperProps={{
              style: { zIndex: 9005 },
            }}
          >
            <IconButton
              onMouseDown={() => handleMoveStart(0, 0, -0.1)}
              onMouseUp={handleStop}
              onTouchStart={() => handleMoveStart(0, 0, -0.1)}
              onTouchEnd={handleStop}
              sx={{ bgcolor: "action.hover" }}
              disabled={!supportsZoom}
            >
              <ZoomOut size={24} />
            </IconButton>
          </Tooltip>
        </Box>

        {/* Speed Control Slider */}
        <FormControl>
          <Typography variant="subtitle2" gutterBottom>
            Speed: {Math.round(moveSpeed * 100)}%
          </Typography>
          <Slider
            value={moveSpeed}
            onChange={(_, value) => setMoveSpeed(value as number)}
            min={speedMinMax.panTiltMin || 0.0}
            max={speedMinMax.panTiltMax || 1.0}
            step={0.05}
            size="small"
            valueLabelDisplay="auto"
            valueLabelFormat={(value) => `${Math.round(value * 100)}%`}
          />
        </FormControl>

        {/* Reverse Controls */}
        <Box
          sx={{
            pl: 0.5,
            mt: 2,
            mb: 1,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <FormControlLabel
            control={
              <Switch
                checked={reversePan}
                onChange={(e) => setReversePan(e.target.checked)}
                size="small"
              />
            }
            label="Reverse Pan"
            slotProps={{ typography: { variant: "body2" } }}
          />
          <FormControlLabel
            control={
              <Switch
                checked={reverseTilt}
                onChange={(e) => setReverseTilt(e.target.checked)}
                size="small"
              />
            }
            label="Reverse Tilt"
            slotProps={{ typography: { variant: "body2" } }}
          />
        </Box>

        {/* Action Buttons */}
        <Box mb={2} mt={2}>
          {supportsHome && (
            <Tooltip
              title="Go to Home Position"
              PopperProps={{
                style: { zIndex: 9005 },
              }}
              placement="left"
              arrow
            >
              <Button
                variant="outlined"
                fullWidth
                startIcon={<Home size={16} />}
                onClick={handleGoHome}
                sx={{
                  mb: 1,
                  textTransform: "none",
                  justifyContent: "flex-start",
                }}
              >
                HOME
              </Button>
            </Tooltip>
          )}
          {supportsPresets && (
            <>
              <Tooltip
                title="Manage PTZ Presets"
                PopperProps={{
                  style: { zIndex: 9005 },
                }}
                placement="left"
                arrow
              >
                <Button
                  variant="outlined"
                  fullWidth
                  startIcon={<ImageSearchAlt size={16} />}
                  onClick={() => setPresetsDialogOpen(true)}
                  sx={{
                    mb: 1,
                    textTransform: "none",
                    justifyContent: "flex-start",
                  }}
                >
                  PRESETS
                </Button>
              </Tooltip>
              <Tooltip
                title="Save Current Position as Preset"
                PopperProps={{
                  style: { zIndex: 9005 },
                }}
                placement="left"
                arrow
              >
                <Button
                  variant="outlined"
                  fullWidth
                  startIcon={<DataCollection size={16} />}
                  onClick={() => setSavePresetDialogOpen(true)}
                  color="success"
                  sx={{
                    mb: 1,
                    textTransform: "none",
                    justifyContent: "flex-start",
                  }}
                >
                  SAVE PRESET
                </Button>
              </Tooltip>
            </>
          )}
          {supportsHome && (
            <Tooltip
              title="Save Current Position as Home"
              PopperProps={{
                style: { zIndex: 9005 },
              }}
              placement="left"
              arrow
            >
              <Button
                variant="outlined"
                fullWidth
                startIcon={<Flag size={16} />}
                onClick={() => setSetHomeDialogOpen(true)}
                color="success"
                sx={{
                  textTransform: "none",
                  justifyContent: "flex-start",
                }}
              >
                SET HOME
              </Button>
            </Tooltip>
          )}
        </Box>
      </Drawer>

      {/* Presets Dialog */}
      <Dialog
        open={presetsDialogOpen}
        onClose={() => setPresetsDialogOpen(false)}
        maxWidth="sm"
        fullWidth
        sx={{
          zIndex: 9005,
        }}
      >
        <DialogTitle>
          <Stack direction="row" alignItems="center" spacing={1}>
            <ImageSearchAlt size={24} />
            <Typography variant="h6">PTZ Presets</Typography>
          </Stack>
        </DialogTitle>
        <DialogContent>
          {allPresets.length > 0 ? (
            <List>
              {allPresets.map((preset) => (
                <ListItem
                  key={preset.token}
                  disablePadding
                  secondaryAction={
                    preset.type !== "user_defined" ? (
                      <Tooltip
                        title="Remove Preset"
                        PopperProps={{
                          style: { zIndex: 9005 },
                        }}
                      >
                        <IconButton
                          edge="end"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedPresetToken(preset.token);
                            setSelectedPresetName(preset.Name || preset.token);
                            setRemovePresetDialogOpen(true);
                          }}
                          size="small"
                          color="error"
                        >
                          <TrashCan size={20} />
                        </IconButton>
                      </Tooltip>
                    ) : null
                  }
                >
                  <Tooltip
                    title={`Go to ${preset.Name || preset.token}`}
                    PopperProps={{
                      style: { zIndex: 9005 },
                    }}
                  >
                    <ListItemButton
                      onClick={() => {
                        if (preset.type === "user_defined") {
                          // Absolute move
                          if (preset.PTZPosition?.PanTilt) {
                            handleAbsoluteMove(
                              preset.PTZPosition.PanTilt.x,
                              preset.PTZPosition.PanTilt.y,
                              preset.PTZPosition.Zoom?.x ?? undefined,
                              false, // Not adjusted/reversed for user-defined presets
                            );
                          }
                        } else {
                          handleGotoPreset(preset.token);
                        }
                      }}
                    >
                      <ListItemIcon sx={{ minWidth: 35 }}>
                        {preset.type === "user_defined" ? (
                          <ZAxis size={20} />
                        ) : (
                          <DataCollection size={20} />
                        )}
                      </ListItemIcon>
                      <ListItemText
                        primary={preset.Name || preset.token}
                        secondary={
                          preset.type !== "user_defined"
                            ? preset.PTZPosition
                              ? `Token: ${preset.token}, Pan: ${preset.PTZPosition.PanTilt?.x?.toFixed(2) ?? "N/A"}, Tilt: ${preset.PTZPosition.PanTilt?.y?.toFixed(2) ?? "N/A"}, Zoom: ${preset.PTZPosition.Zoom?.x?.toFixed(2) ?? "N/A"}`
                              : `Token: ${preset.token}`
                            : preset.PTZPosition
                              ? `On Startup: ${preset.move_on_startup}, Pan: ${preset.PTZPosition.PanTilt?.x?.toFixed(2) ?? "N/A"}, Tilt: ${preset.PTZPosition.PanTilt?.y?.toFixed(2) ?? "N/A"}, Zoom: ${preset.PTZPosition.Zoom?.x?.toFixed(2) ?? "N/A"}`
                              : `Token: ${preset.token}`
                        }
                      />
                    </ListItemButton>
                  </Tooltip>
                </ListItem>
              ))}
            </List>
          ) : (
            <Typography color="text.secondary" align="center" sx={{ py: 3 }}>
              No presets available
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPresetsDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Save Preset Dialog */}
      <Dialog
        open={savePresetDialogOpen}
        onClose={() => {
          setSavePresetDialogOpen(false);
          setNewPresetName("");
        }}
        maxWidth="sm"
        fullWidth
        sx={{
          zIndex: 9005,
        }}
      >
        <DialogTitle>
          <Stack direction="row" alignItems="center" spacing={1}>
            <DataCollection size={24} />
            <Typography variant="h6">
              Save Current Position as Preset
            </Typography>
          </Stack>
        </DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Preset Name"
            type="text"
            fullWidth
            variant="outlined"
            value={newPresetName}
            onChange={(e) => setNewPresetName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleSavePreset(newPresetName);
              }
            }}
          />
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setSavePresetDialogOpen(false);
              setNewPresetName("");
            }}
          >
            Cancel
          </Button>
          <Button
            onClick={() => handleSavePreset(newPresetName)}
            variant="contained"
            disabled={
              !newPresetName.trim() || mutations.setPresetMutation.isPending
            }
          >
            {mutations.setPresetMutation.isPending ? (
              <CircularProgress size={24} />
            ) : (
              "Save"
            )}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Set Home Confirmation Dialog */}
      <Dialog
        open={setHomeDialogOpen}
        onClose={() => setSetHomeDialogOpen(false)}
        maxWidth="sm"
        fullWidth
        sx={{
          zIndex: 9005,
        }}
      >
        <DialogTitle>
          <Stack direction="row" alignItems="center" spacing={1}>
            <Flag size={24} />
            <Typography variant="h6">Set Home Position</Typography>
          </Stack>
        </DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to set the current camera position as the home
            position? This will override the existing home position.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSetHomeDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleSetHome}
            variant="contained"
            color="success"
            disabled={mutations.setHomeMutation.isPending}
          >
            {mutations.setHomeMutation.isPending ? (
              <CircularProgress size={24} />
            ) : (
              "Confirm"
            )}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Remove Preset Confirmation Dialog */}
      <Dialog
        open={removePresetDialogOpen}
        onClose={() => setRemovePresetDialogOpen(false)}
        maxWidth="sm"
        fullWidth
        sx={{
          zIndex: 9005,
        }}
      >
        <DialogTitle>
          <Stack direction="row" alignItems="center" spacing={1}>
            <TrashCan size={24} />
            <Typography variant="h6">Remove Preset</Typography>
          </Stack>
        </DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to remove preset &quot;{selectedPresetName}
            &quot;? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRemovePresetDialogOpen(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              handleRemovePreset(selectedPresetToken);
              setRemovePresetDialogOpen(false);
            }}
            variant="contained"
            color="error"
            disabled={mutations.removePresetMutation.isPending}
          >
            {mutations.removePresetMutation.isPending ? (
              <CircularProgress size={24} />
            ) : (
              "Remove"
            )}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
