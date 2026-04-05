import {
  AddAlt,
  Flag,
  Help,
  Home,
  Information,
  TrashCan,
} from "@carbon/icons-react";
import {
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useState } from "react";

import { GrowingSpinner } from "components/loading/GrowingSpinner";
import { useToast } from "hooks/UseToast";
import {
  useGetPtzPresets,
  useGetPtzStatus,
  usePtzGotoHome,
  usePtzGotoPreset,
  usePtzRemovePreset,
  usePtzSetHome,
  usePtzSetPreset,
} from "lib/api/actions/onvif/ptz";
import * as onvif_types from "lib/api/actions/onvif/types";
import * as types from "lib/types";

import { QueryWrapper } from "../../config/QueryWrapper";

interface PTZPositionsProps {
  cameraIdentifier: string;
  ptzNodes?: onvif_types.PtzNodesResponse;
  isLoading: boolean;
  isError: boolean;
  error: types.APIErrorResponse | null;
}

export function PTZPositions({
  cameraIdentifier,
  ptzNodes,
  isLoading: nodesLoading,
  isError: nodesIsError,
  error: nodesError,
}: PTZPositionsProps) {
  const TITLE = "PTZ Positions";
  const DESC = "Manage all types of PTZ operations related to positions.";

  const toast = useToast();

  // ONVIF API hooks
  const {
    data: presetsData,
    isLoading: presetsLoading,
    isError: presetsIsError,
    error: presetsError,
  } = useGetPtzPresets(cameraIdentifier, "onvif");

  const {
    data: statusData,
    isLoading: statusLoading,
    isError: statusIsError,
    error: statusError,
  } = useGetPtzStatus(cameraIdentifier);

  const gotoHomeMutation = usePtzGotoHome();
  const setHomeMutation = usePtzSetHome();
  const gotoPresetMutation = usePtzGotoPreset();
  const setPresetMutation = usePtzSetPreset();
  const removePresetMutation = usePtzRemovePreset();

  // Extract capabilities from nodes
  const ptzNode = ptzNodes?.nodes?.[0];
  const supportsPresets =
    ptzNode?.MaximumNumberOfPresets && ptzNode.MaximumNumberOfPresets > 0;
  const supportsHome = ptzNode?.HomeSupported === true;

  // Combine loading and error states
  const isLoading = nodesLoading || presetsLoading || statusLoading;
  const isError = nodesIsError || presetsIsError || statusIsError;
  const error = nodesError || presetsError || statusError;

  const [isGotoHomeLoading, setIsGotoHomeLoading] = useState(false);
  const [isSetHomeLoading, setIsSetHomeLoading] = useState(false);
  const [gotoPresetLoading, setGotoPresetLoading] = useState<string | null>(
    null,
  );
  const [removingPreset, setRemovingPreset] = useState<string | null>(null);

  const [addPresetDialogOpen, setAddPresetDialogOpen] = useState(false);
  const [setHomeDialogOpen, setSetHomeDialogOpen] = useState(false);
  const [removePresetDialogOpen, setRemovePresetDialogOpen] = useState(false);
  const [newPresetName, setNewPresetName] = useState("");
  const [selectedPresetToken, setSelectedPresetToken] = useState<string>("");
  const [selectedPresetName, setSelectedPresetName] = useState<string>("");

  const handleGotoHome = () => {
    setIsGotoHomeLoading(true);
    gotoHomeMutation.mutate(
      { cameraIdentifier },
      {
        onSuccess: () => {
          toast.success("Moved to home position successfully");
          setIsGotoHomeLoading(false);
        },
        onError: (err) => {
          toast.error(err?.message || "Failed to go to home position");
          setIsGotoHomeLoading(false);
        },
      },
    );
  };

  const handleSetHome = () => {
    setIsSetHomeLoading(true);
    setHomeMutation.mutate(
      { cameraIdentifier },
      {
        onSuccess: () => {
          toast.success("Home position set successfully");
          setIsSetHomeLoading(false);
          setSetHomeDialogOpen(false);
        },
        onError: (err) => {
          toast.error(err?.message || "Failed to set home position");
          setIsSetHomeLoading(false);
        },
      },
    );
  };

  const handleGotoPreset = (presetToken: string, presetName?: string) => {
    setGotoPresetLoading(presetToken);
    gotoPresetMutation.mutate(
      { cameraIdentifier, presetToken },
      {
        onSuccess: () => {
          toast.success(
            `Moved to preset ${presetName || presetToken} successfully`,
          );
          setGotoPresetLoading(null);
        },
        onError: (err) => {
          toast.error(
            err?.message ||
              `Failed to go to preset ${presetName || presetToken}`,
          );
          setGotoPresetLoading(null);
        },
      },
    );
  };

  const handleAddPreset = () => {
    if (!newPresetName.trim()) {
      toast.error("Preset name cannot be empty");
      return;
    }

    setPresetMutation.mutate(
      { cameraIdentifier, presetName: newPresetName.trim() },
      {
        onSuccess: () => {
          toast.success(`Preset "${newPresetName}" created successfully`);
          setAddPresetDialogOpen(false);
          setNewPresetName("");
        },
        onError: (err) => {
          toast.error(err?.message || "Failed to create preset");
        },
      },
    );
  };

  const handleRemovePreset = () => {
    setRemovingPreset(selectedPresetToken);
    removePresetMutation.mutate(
      { cameraIdentifier, presetToken: selectedPresetToken },
      {
        onSuccess: () => {
          toast.success(
            `Preset ${selectedPresetName || selectedPresetToken} removed successfully`,
          );
          setRemovingPreset(null);
          setRemovePresetDialogOpen(false);
        },
        onError: (err) => {
          toast.error(
            err?.message ||
              `Failed to remove preset ${selectedPresetName || selectedPresetToken}`,
          );
          setRemovingPreset(null);
        },
      },
    );
  };

  const presets = presetsData?.presets || [];
  const hasPresets = presets.length > 0;
  const maxPresets = ptzNode?.MaximumNumberOfPresets || 0;

  // Check if any features are supported
  const hasAnySupport = supportsHome || supportsPresets;

  return (
    <QueryWrapper
      isLoading={isLoading}
      isError={isError}
      errorMessage={error?.message || "Failed to load PTZ positions"}
      isEmpty={!hasAnySupport}
      emptyMessage="No PTZ position features available"
      title={TITLE}
    >
      <Box>
        <Box
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          mb={1.5}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Typography variant="subtitle2">{TITLE}</Typography>
            <Tooltip title={DESC} arrow placement="top">
              <Help size={16} />
            </Tooltip>
          </Box>
        </Box>

        <Box display="flex" flexDirection="column" gap={1.5}>
          {/* Position Status Section */}
          {statusData?.status && (
            <Box
              sx={{
                display: "flex",
                flexDirection: "column",
                gap: 1,
                border: 1,
                borderColor: "divider",
                borderRadius: 1,
                p: 1.5,
              }}
            >
              <Box display="flex" alignItems="center" gap={1}>
                <Tooltip
                  title="RREAD-ONLY: PTZ status information including current position and movement state."
                  arrow
                  placement="top"
                >
                  <Information size={16} />
                </Tooltip>
                <Typography variant="subtitle2">Position Status</Typography>
              </Box>

              <Box display="flex" flexDirection="column" gap={1}>
                {/* Current Position */}
                {statusData.status.Position && (
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Current Position:
                    </Typography>
                    <Box sx={{ pl: 1 }}>
                      {statusData.status.Position.PanTilt && (
                        <Typography variant="body2">
                          Pan:{" "}
                          {statusData.status.Position.PanTilt.x?.toFixed(3) ??
                            "N/A"}
                          , Tilt:{" "}
                          {statusData.status.Position.PanTilt.y?.toFixed(3) ??
                            "N/A"}
                        </Typography>
                      )}
                      {statusData.status.Position.Zoom && (
                        <Typography variant="body2">
                          Zoom:{" "}
                          {statusData.status.Position.Zoom.x?.toFixed(3) ??
                            "N/A"}
                        </Typography>
                      )}
                    </Box>
                  </Box>
                )}

                {/* Move Status */}
                {statusData.status.MoveStatus && (
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Move Status:
                    </Typography>
                    <Box sx={{ pl: 1 }}>
                      {statusData.status.MoveStatus.PanTilt && (
                        <Typography variant="body2">
                          Pan/Tilt: {statusData.status.MoveStatus.PanTilt}
                        </Typography>
                      )}
                      {statusData.status.MoveStatus.Zoom && (
                        <Typography variant="body2">
                          Zoom: {statusData.status.MoveStatus.Zoom}
                        </Typography>
                      )}
                    </Box>
                  </Box>
                )}

                {/* Error Status */}
                {typeof statusData.status.Error === "string" &&
                  statusData.status.Error !== "0" &&
                  statusData.status.Error !== "NO error" && (
                    <Box>
                      <Typography variant="caption" color="error">
                        Error:
                      </Typography>
                      <Typography variant="body2" color="error" sx={{ pl: 1 }}>
                        {statusData.status.Error}
                      </Typography>
                    </Box>
                  )}

                {/* Last Updated */}
                {statusData.status.UtcTime && (
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Last Updated:
                    </Typography>
                    <Box sx={{ pl: 1 }}>
                      <Typography variant="body2">
                        {statusData.status.UtcTime}
                      </Typography>
                    </Box>
                  </Box>
                )}
              </Box>
            </Box>
          )}

          {/* Home Position Section */}
          {supportsHome && (
            <Box
              sx={{
                display: "flex",
                flexDirection: "column",
                gap: 1.5,
                border: 1,
                borderColor: "divider",
                borderRadius: 1,
                p: 1.5,
              }}
            >
              <Box display="flex" alignItems="center" gap={1}>
                <Tooltip
                  title="The home position is a predefined PTZ position that the camera can return to."
                  arrow
                  placement="top"
                >
                  <Information size={16} />
                </Tooltip>
                <Typography variant="subtitle2">Home Position</Typography>
              </Box>
              <Box display="flex" gap={1}>
                <Button
                  variant="contained"
                  color="primary"
                  fullWidth
                  startIcon={
                    isGotoHomeLoading ? (
                      <GrowingSpinner color="primary.main" size={16} />
                    ) : (
                      <Home size={16} />
                    )
                  }
                  onClick={handleGotoHome}
                  disabled={isGotoHomeLoading}
                >
                  {isGotoHomeLoading ? "Moving..." : "Go to Home"}
                </Button>
                <Button
                  variant="contained"
                  color="success"
                  fullWidth
                  startIcon={<Flag size={16} />}
                  onClick={() => setSetHomeDialogOpen(true)}
                >
                  Set Home
                </Button>
              </Box>
            </Box>
          )}

          {/* Presets Section */}
          {supportsPresets && (
            <Box
              sx={{
                display: "flex",
                flexDirection: "column",
                gap: 1,
                border: 1,
                borderColor: "divider",
                borderRadius: 1,
                p: 1.5,
              }}
            >
              <Box
                display="flex"
                justifyContent="space-between"
                alignItems="center"
              >
                <Box display="flex" alignItems="center" gap={1}>
                  <Tooltip
                    title="Presets are predefined PTZ positions that can be quickly accessed."
                    arrow
                    placement="top"
                  >
                    <Information size={16} />
                  </Tooltip>
                  <Typography variant="subtitle2">PTZ Presets</Typography>
                </Box>
                <Button
                  size="small"
                  startIcon={<AddAlt size={16} />}
                  onClick={() => setAddPresetDialogOpen(true)}
                >
                  Add
                </Button>
              </Box>

              {hasPresets ? (
                <List dense>
                  {presets.map((preset) => (
                    <ListItem
                      key={preset.token}
                      disablePadding
                      secondaryAction={
                        <Tooltip title="Remove Preset" arrow placement="top">
                          <IconButton
                            edge="end"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedPresetToken(preset.token);
                              setSelectedPresetName(
                                preset.Name || preset.token,
                              );
                              setRemovePresetDialogOpen(true);
                            }}
                            size="small"
                            color="error"
                          >
                            <TrashCan size={20} />
                          </IconButton>
                        </Tooltip>
                      }
                    >
                      <Tooltip
                        title={`Go to ${preset.Name || preset.token}`}
                        arrow
                        placement="top"
                      >
                        <ListItemButton
                          onClick={() =>
                            handleGotoPreset(preset.token, preset.Name)
                          }
                          disabled={gotoPresetLoading === preset.token}
                        >
                          <ListItemText
                            primary={preset.Name || "Unnamed"}
                            secondary={
                              preset.PTZPosition
                                ? `Token: ${preset.token}, Pan: ${preset.PTZPosition.PanTilt?.x?.toFixed(2) ?? "N/A"}, Tilt: ${preset.PTZPosition.PanTilt?.y?.toFixed(2) ?? "N/A"}${preset.PTZPosition.Zoom?.x?.toFixed(2) ? `, Zoom: ${preset.PTZPosition.Zoom?.x?.toFixed(2)}` : ""}`
                                : `Token: ${preset.token}`
                            }
                          />
                        </ListItemButton>
                      </Tooltip>
                    </ListItem>
                  ))}
                </List>
              ) : (
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                    py: 2,
                  }}
                >
                  <Typography variant="body2" color="text.secondary">
                    No presets available.
                  </Typography>
                </Box>
              )}
            </Box>
          )}
        </Box>

        {/* Add Preset Dialog */}
        <Dialog
          open={addPresetDialogOpen}
          onClose={() => {
            setAddPresetDialogOpen(false);
            setNewPresetName("");
          }}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>
            <Box
              display="flex"
              justifyContent="space-between"
              alignItems="center"
              gap={1}
            >
              <Typography variant="inherit">Add New Preset</Typography>
              <Typography variant="caption" fontWeight="medium" color="primary">
                {`Max Presets: ${maxPresets}`}
              </Typography>
            </Box>
          </DialogTitle>
          <DialogContent>
            <Box sx={{ pt: 1 }}>
              <TextField
                autoFocus
                fullWidth
                label="Preset Name"
                value={newPresetName}
                onChange={(e) => setNewPresetName(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === "Enter") {
                    handleAddPreset();
                  }
                }}
                helperText="The camera will save its current position with this name"
              />
            </Box>
          </DialogContent>
          <DialogActions>
            <Button
              onClick={() => {
                setAddPresetDialogOpen(false);
                setNewPresetName("");
              }}
            >
              Cancel
            </Button>
            <Button
              variant="contained"
              onClick={handleAddPreset}
              disabled={!newPresetName.trim() || setPresetMutation.isPending}
            >
              {setPresetMutation.isPending ? (
                <CircularProgress enableTrackSlot size={24} />
              ) : (
                "Add"
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
        >
          <DialogTitle>
            <Stack direction="row" alignItems="center" spacing={1}>
              <Flag size={24} />
              <Typography variant="h6">Set Home Position</Typography>
            </Stack>
          </DialogTitle>
          <DialogContent>
            <DialogContentText>
              Are you sure you want to set the current camera position as the
              home position? This will override the existing home position.
            </DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setSetHomeDialogOpen(false)}>Cancel</Button>
            <Button
              onClick={handleSetHome}
              variant="contained"
              color="success"
              disabled={isSetHomeLoading}
            >
              {isSetHomeLoading ? (
                <CircularProgress enableTrackSlot size={24} />
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
        >
          <DialogTitle>
            <Stack direction="row" alignItems="center" spacing={1}>
              <TrashCan size={24} />
              <Typography variant="h6">Remove Preset</Typography>
            </Stack>
          </DialogTitle>
          <DialogContent>
            <DialogContentText>
              Are you sure you want to remove preset &quot;{selectedPresetName}
              &quot;? This action cannot be undone.
            </DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setRemovePresetDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleRemovePreset}
              variant="contained"
              color="error"
              disabled={removingPreset === selectedPresetToken}
            >
              {removingPreset === selectedPresetToken ? (
                <CircularProgress enableTrackSlot size={24} />
              ) : (
                "Remove"
              )}
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </QueryWrapper>
  );
}
