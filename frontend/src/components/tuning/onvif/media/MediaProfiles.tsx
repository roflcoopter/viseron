import { AddAlt, Help, ProgressBarRound, TrashCan } from "@carbon/icons-react";
import {
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { MouseEvent, useState } from "react";

import { useToast } from "hooks/UseToast";
import {
  useCreateMediaProfile,
  useDeleteMediaProfile,
  useGetMediaProfiles,
} from "lib/api/actions/onvif/media";

import { QueryWrapper } from "../../config/QueryWrapper";

interface MediaProfilesProps {
  cameraIdentifier: string;
  mediaCapabilities?: any;
}

export function MediaProfiles({
  cameraIdentifier,
  mediaCapabilities,
}: MediaProfilesProps) {
  const TITLE = "Media Profiles";
  const DESC =
    "Manage ONVIF media profiles, which define the video and audio settings for the camera.";

  const toast = useToast();

  // ONVIF API hooks
  const { data, isLoading, isError, error } =
    useGetMediaProfiles(cameraIdentifier);
  const createProfileMutation = useCreateMediaProfile(cameraIdentifier);
  const deleteProfileMutation = useDeleteMediaProfile(cameraIdentifier);

  const profiles = data?.profiles;

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<"add" | "view">("add");
  const [profileName, setProfileName] = useState("");
  const [profileToken, setProfileToken] = useState("");
  const [selectedProfile, setSelectedProfile] = useState<any>(null);

  // Context menu
  const [contextMenu, setContextMenu] = useState<{
    mouseX: number;
    mouseY: number;
    profile: any;
  } | null>(null);

  const handleContextMenu = (
    event: MouseEvent<HTMLButtonElement>,
    profile: any,
  ) => {
    event.preventDefault();
    setContextMenu({
      mouseX: event.clientX,
      mouseY: event.clientY,
      profile,
    });
  };

  const handleContextMenuClose = () => {
    setContextMenu(null);
  };

  // Handlers
  const handleAddProfile = () => {
    setDialogMode("add");
    setProfileName("");
    setProfileToken("");
    setSelectedProfile(null);
    setDialogOpen(true);
  };

  const handleViewProfile = (profile: any) => {
    setDialogMode("view");
    setSelectedProfile(profile);
    setProfileName(profile.Name);
    setProfileToken(profile.token);
    setDialogOpen(true);
  };

  const handleDialogClose = () => {
    setDialogOpen(false);
  };

  const handleCreateProfile = () => {
    if (profileName) {
      createProfileMutation.mutate(
        {
          name: profileName,
          token: profileToken || undefined,
        },
        {
          onSuccess: () => {
            toast.success(`Profile "${profileName}" created successfully`);
            handleDialogClose();
          },
          onError: (err) => {
            toast.error(err?.message || "Failed to create profile");
          },
        },
      );
    }
  };

  const handleDeleteProfile = (profile: any) => {
    deleteProfileMutation.mutate(profile.token, {
      onSuccess: () => {
        toast.success(`Profile "${profile.Name}" deleted successfully`);
        handleDialogClose();
      },
      onError: (err) => {
        toast.error(err?.message || "Failed to delete profile");
      },
    });
  };

  // Helper to format resolution
  const formatResolution = (profile: any) => {
    const video = profile.VideoEncoderConfiguration;
    if (video?.Resolution) {
      return `${video.Resolution.Width}x${video.Resolution.Height}`;
    }
    return null;
  };

  // Helper to format encoding info
  const formatEncoding = (profile: any) => {
    const video = profile.VideoEncoderConfiguration;
    if (video) {
      const parts = [];
      if (video.Encoding) parts.push(video.Encoding);
      if (video.RateControl?.FrameRateLimit)
        parts.push(`${video.RateControl.FrameRateLimit}fps`);
      if (video.RateControl?.BitrateLimit)
        parts.push(`${video.RateControl.BitrateLimit}kbps`);
      return parts.join(" • ");
    }
    return null;
  };

  return (
    <QueryWrapper
      isLoading={isLoading}
      isError={isError}
      errorMessage={error?.message || "Failed to load media profiles"}
      isEmpty={data?.profiles?.length === 0}
      title={TITLE}
    >
      <Box>
        <Box
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          mb={1}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Typography variant="subtitle2">{TITLE}</Typography>
            <Tooltip title={DESC} arrow placement="top">
              <Help size={16} />
            </Tooltip>
          </Box>
          <Button
            size="small"
            startIcon={<AddAlt size={16} />}
            onClick={handleAddProfile}
          >
            Add
          </Button>
        </Box>

        {/* Profiles List */}
        {profiles && profiles.length > 0 && (
          <Box display="flex" flexDirection="column" gap={1}>
            {profiles.map((profile) => (
              <Button
                key={profile.token}
                variant="outlined"
                fullWidth
                onContextMenu={(e) => handleContextMenu(e, profile)}
                onClick={() => handleViewProfile(profile)}
                sx={{
                  p: 1.5,
                  display: "flex",
                  justifyContent: "flex-start",
                  textTransform: "none",
                }}
                color="inherit"
              >
                <ProgressBarRound
                  size={20}
                  style={{ marginRight: 8, flexShrink: 0 }}
                />
                <Box
                  sx={{
                    flexGrow: 1,
                    textAlign: "left",
                    overflow: "hidden",
                  }}
                >
                  <Typography
                    variant="body2"
                    sx={{
                      fontWeight: 500,
                    }}
                  >
                    {profile.Name}
                  </Typography>
                  {formatEncoding(profile) && (
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ display: "block" }}
                    >
                      {formatEncoding(profile)}
                    </Typography>
                  )}
                </Box>
                <Box sx={{ flexShrink: 0, textAlign: "right" }}>
                  {formatResolution(profile) && (
                    <Typography variant="caption" color="text.secondary">
                      {formatResolution(profile)}
                    </Typography>
                  )}
                  {profile.fixed && (
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ display: "block" }}
                    >
                      Fixed
                    </Typography>
                  )}
                </Box>
              </Button>
            ))}
          </Box>
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
                handleDeleteProfile(contextMenu.profile);
              }
              handleContextMenuClose();
            }}
            disabled={contextMenu?.profile?.fixed || contextMenu == null}
            sx={{ color: "error.main" }}
          >
            <ListItemIcon sx={{ color: "error.main" }}>
              <TrashCan />
            </ListItemIcon>
            <ListItemText>Delete</ListItemText>
          </MenuItem>
        </Menu>

        {/* Add/View Profile Dialog */}
        <Dialog
          open={dialogOpen}
          onClose={handleDialogClose}
          maxWidth={dialogMode === "add" ? "sm" : "md"}
          fullWidth
        >
          <DialogTitle>
            <Box
              display="flex"
              justifyContent="space-between"
              alignItems="center"
              gap={1}
            >
              <Typography variant="inherit">
                {dialogMode === "add" ? "Add Profile" : "Profile Details"}
              </Typography>
              {mediaCapabilities?.ProfileCapabilities
                ?.MaximumNumberOfProfiles &&
                dialogMode === "add" && (
                  <Typography
                    variant="caption"
                    fontWeight="medium"
                    color="primary"
                  >
                    {`Max Profiles: ${mediaCapabilities.ProfileCapabilities.MaximumNumberOfProfiles}`}
                  </Typography>
                )}
              {selectedProfile?.fixed && (
                <Typography
                  variant="caption"
                  fontWeight="medium"
                  color="warning.main"
                >
                  Fixed Profile (READ-ONLY)
                </Typography>
              )}
            </Box>
          </DialogTitle>
          <DialogContent>
            <Stack direction="column" spacing={2} pt={2} mb={1}>
              <TextField
                autoFocus={dialogMode === "add"}
                margin="dense"
                label="Profile Name"
                fullWidth
                variant="outlined"
                value={profileName}
                onChange={(e) => setProfileName(e.target.value)}
                slotProps={{
                  input: {
                    readOnly: dialogMode === "view",
                  },
                }}
              />
              <TextField
                margin="dense"
                label="Profile Token"
                fullWidth
                variant="outlined"
                value={profileToken}
                onChange={(e) => setProfileToken(e.target.value)}
                helperText={
                  dialogMode === "add"
                    ? "Optional. Leave empty to auto-generate."
                    : undefined
                }
                slotProps={{
                  input: {
                    readOnly: dialogMode === "view",
                  },
                }}
              />
            </Stack>

            {/* Profile Details (View Mode) */}
            {dialogMode === "view" && selectedProfile && (
              <Box
                sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}
              >
                {/* Video Source Configuration */}
                {selectedProfile.VideoSourceConfiguration && (
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>
                      Video Source Configuration
                    </Typography>
                    <Box
                      sx={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 2,
                        mt: 2,
                      }}
                    >
                      <Stack direction="row" spacing={2} alignItems="center">
                        <TextField
                          fullWidth
                          label="Name"
                          value={selectedProfile.VideoSourceConfiguration.Name}
                          placeholder="Name"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Use Count"
                          value={
                            selectedProfile.VideoSourceConfiguration.UseCount
                          }
                          placeholder="Use Count"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                      </Stack>
                      <Stack direction="row" spacing={2} alignItems="center">
                        <TextField
                          fullWidth
                          label="Token"
                          value={selectedProfile.VideoSourceConfiguration.token}
                          placeholder="Token"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Source Token"
                          value={
                            selectedProfile.VideoSourceConfiguration.SourceToken
                          }
                          placeholder="Source Token"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        {selectedProfile.VideoSourceConfiguration.ViewMode && (
                          <TextField
                            fullWidth
                            label="View Mode"
                            value={
                              selectedProfile.VideoSourceConfiguration.ViewMode
                            }
                            placeholder="View Mode"
                            slotProps={{
                              input: {
                                readOnly: dialogMode === "view",
                              },
                            }}
                          />
                        )}
                      </Stack>
                      <Stack direction="row" spacing={2} alignItems="center">
                        <TextField
                          fullWidth
                          label="Bound X"
                          value={
                            selectedProfile.VideoSourceConfiguration.Bounds.x
                          }
                          placeholder="Bound X"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Bound Y"
                          value={
                            selectedProfile.VideoSourceConfiguration.Bounds.y
                          }
                          placeholder="Bound Y"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Bound Width"
                          value={
                            selectedProfile.VideoSourceConfiguration.Bounds
                              .width
                          }
                          placeholder="Bound Width"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Bound Height"
                          value={
                            selectedProfile.VideoSourceConfiguration.Bounds
                              .height
                          }
                          placeholder="Bound Height"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                      </Stack>
                    </Box>
                  </Box>
                )}

                {/* Audio Source Configuration */}
                {selectedProfile.AudioSourceConfiguration && (
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>
                      Audio Source Configuration
                    </Typography>
                    <Box
                      sx={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 2,
                        mt: 2,
                      }}
                    >
                      <Stack direction="row" spacing={2} alignItems="center">
                        <TextField
                          fullWidth
                          label="Name"
                          value={selectedProfile.AudioSourceConfiguration.Name}
                          placeholder="Name"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Use Count"
                          value={
                            selectedProfile.AudioSourceConfiguration.UseCount
                          }
                          placeholder="Use Count"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                      </Stack>
                      <Stack direction="row" spacing={2} alignItems="center">
                        <TextField
                          fullWidth
                          label="Token"
                          value={selectedProfile.AudioSourceConfiguration.token}
                          placeholder="Token"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Source Token"
                          value={
                            selectedProfile.AudioSourceConfiguration.SourceToken
                          }
                          placeholder="Source Token"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                      </Stack>
                    </Box>
                  </Box>
                )}

                {/* Video Encoder Configuration */}
                {selectedProfile.VideoEncoderConfiguration && (
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>
                      Video Encoder Configuration
                    </Typography>
                    <Box
                      sx={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 2,
                        mt: 2,
                      }}
                    >
                      <Stack direction="row" spacing={2} alignItems="center">
                        <TextField
                          fullWidth
                          label="Name"
                          value={selectedProfile.VideoEncoderConfiguration.Name}
                          placeholder="Name"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Use Count"
                          value={
                            selectedProfile.VideoEncoderConfiguration.UseCount
                          }
                          placeholder="Use Count"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                      </Stack>
                      <Stack direction="row" spacing={2} alignItems="center">
                        <TextField
                          fullWidth
                          label="Token"
                          value={
                            selectedProfile.VideoEncoderConfiguration.token
                          }
                          placeholder="Token"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Session Timeout"
                          value={
                            selectedProfile.VideoEncoderConfiguration
                              .SessionTimeout
                          }
                          placeholder="Session Timeout"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                      </Stack>
                      <Stack direction="row" spacing={2} alignItems="center">
                        <TextField
                          fullWidth
                          label="Encoding"
                          value={
                            selectedProfile.VideoEncoderConfiguration.Encoding
                          }
                          placeholder="Encoding"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Quality"
                          value={
                            selectedProfile.VideoEncoderConfiguration.Quality
                          }
                          placeholder="Quality"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                      </Stack>
                      {selectedProfile.VideoEncoderConfiguration.Resolution && (
                        <Stack direction="row" spacing={2} alignItems="center">
                          <TextField
                            fullWidth
                            label="Width"
                            value={
                              selectedProfile.VideoEncoderConfiguration
                                .Resolution.Width
                            }
                            placeholder="Width"
                            slotProps={{
                              input: {
                                readOnly: dialogMode === "view",
                              },
                            }}
                          />
                          <TextField
                            fullWidth
                            label="Height"
                            value={
                              selectedProfile.VideoEncoderConfiguration
                                .Resolution.Height
                            }
                            placeholder="Height"
                            slotProps={{
                              input: {
                                readOnly: dialogMode === "view",
                              },
                            }}
                          />
                        </Stack>
                      )}
                      {selectedProfile.VideoEncoderConfiguration
                        .RateControl && (
                        <Stack direction="row" spacing={2} alignItems="center">
                          <TextField
                            fullWidth
                            label="Frame Rate Limit"
                            value={
                              selectedProfile.VideoEncoderConfiguration
                                .RateControl.FrameRateLimit
                            }
                            placeholder="Frame Rate Limit"
                            slotProps={{
                              input: {
                                readOnly: dialogMode === "view",
                              },
                            }}
                          />
                          <TextField
                            fullWidth
                            label="Encoding Interval"
                            value={
                              selectedProfile.VideoEncoderConfiguration
                                .RateControl.EncodingInterval
                            }
                            placeholder="Encoding Interval"
                            slotProps={{
                              input: {
                                readOnly: dialogMode === "view",
                              },
                            }}
                          />
                          <TextField
                            fullWidth
                            label="Bitrate Limit"
                            value={
                              selectedProfile.VideoEncoderConfiguration
                                .RateControl.BitrateLimit
                            }
                            placeholder="Bitrate Limit"
                            slotProps={{
                              input: {
                                readOnly: dialogMode === "view",
                              },
                            }}
                          />
                        </Stack>
                      )}
                    </Box>
                  </Box>
                )}

                {/* Audio Encoder Configuration */}
                {selectedProfile.AudioEncoderConfiguration && (
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>
                      Audio Encoder Configuration
                    </Typography>
                    <Box
                      sx={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 2,
                        mt: 2,
                      }}
                    >
                      <Stack direction="row" spacing={2} alignItems="center">
                        <TextField
                          fullWidth
                          label="Name"
                          value={selectedProfile.AudioEncoderConfiguration.Name}
                          placeholder="Name"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Use Count"
                          value={
                            selectedProfile.AudioEncoderConfiguration.UseCount
                          }
                          placeholder="Use Count"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                      </Stack>
                      <Stack direction="row" spacing={2} alignItems="center">
                        <TextField
                          fullWidth
                          label="Token"
                          value={
                            selectedProfile.AudioEncoderConfiguration.token
                          }
                          placeholder="Token"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Session Timeout"
                          value={
                            selectedProfile.AudioEncoderConfiguration
                              .SessionTimeout
                          }
                          placeholder="Session Timeout"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                      </Stack>
                      <Stack direction="row" spacing={2} alignItems="center">
                        <TextField
                          fullWidth
                          label="Encoding"
                          value={
                            selectedProfile.AudioEncoderConfiguration.Encoding
                          }
                          placeholder="Encoding"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Bitrate"
                          value={
                            selectedProfile.AudioEncoderConfiguration.Bitrate
                          }
                          placeholder="Bitrate"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Sample Rate"
                          value={
                            selectedProfile.AudioEncoderConfiguration.SampleRate
                          }
                          placeholder="Sample Rate"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                      </Stack>
                    </Box>
                  </Box>
                )}

                {/* Video Analytics Configuration */}
                {selectedProfile.VideoAnalyticsConfiguration && (
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>
                      Video Analytics Configuration
                    </Typography>
                    <Box
                      sx={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 2,
                        mt: 2,
                      }}
                    >
                      <Stack direction="row" spacing={2} alignItems="center">
                        <TextField
                          fullWidth
                          label="Name"
                          value={
                            selectedProfile.VideoAnalyticsConfiguration.Name
                          }
                          placeholder="Name"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Use Count"
                          value={
                            selectedProfile.VideoAnalyticsConfiguration.UseCount
                          }
                          placeholder="Use Count"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                      </Stack>
                    </Box>
                  </Box>
                )}

                {/* PTZ Configuration */}
                {selectedProfile.PTZConfiguration && (
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>
                      PTZ Configuration
                    </Typography>
                    <Box
                      sx={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 2,
                        mt: 2,
                      }}
                    >
                      <Stack direction="row" spacing={2} alignItems="center">
                        <TextField
                          fullWidth
                          label="Name"
                          value={selectedProfile.PTZConfiguration.Name}
                          placeholder="Name"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Use Count"
                          value={selectedProfile.PTZConfiguration.UseCount}
                          placeholder="Use Count"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                      </Stack>
                      <Stack direction="row" spacing={2} alignItems="center">
                        <TextField
                          fullWidth
                          label="Token"
                          value={selectedProfile.PTZConfiguration.token}
                          placeholder="Token"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Node Token"
                          value={selectedProfile.PTZConfiguration.NodeToken}
                          placeholder="Node Token"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                      </Stack>
                      <Stack direction="row" spacing={2} alignItems="center">
                        {selectedProfile.PTZConfiguration.DefaultPTZSpeed
                          ?.PanTilt && (
                          <TextField
                            fullWidth
                            label="Default PTZ Speed"
                            value={`x: ${
                              selectedProfile.PTZConfiguration.DefaultPTZSpeed
                                .PanTilt.x
                            }, y: ${selectedProfile.PTZConfiguration.DefaultPTZSpeed.PanTilt.y}, z: ${selectedProfile.PTZConfiguration.DefaultPTZSpeed.PanTilt.z}`}
                            placeholder="Default PTZ Speed"
                            slotProps={{
                              input: {
                                readOnly: dialogMode === "view",
                              },
                            }}
                          />
                        )}
                        <TextField
                          fullWidth
                          label="Default PTZ Timeout"
                          value={
                            selectedProfile.PTZConfiguration.DefaultPTZTimeout
                          }
                          placeholder="Default PTZ Timeout"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                      </Stack>
                      {selectedProfile.PTZConfiguration.PanTiltLimits
                        ?.Range && (
                        <Stack direction="row" spacing={2} alignItems="center">
                          <TextField
                            fullWidth
                            label="Pan Limit"
                            value={`Min: ${selectedProfile.PTZConfiguration.PanTiltLimits.Range.XRange.Min}, Max: ${selectedProfile.PTZConfiguration.PanTiltLimits.Range.XRange.Max}`}
                            placeholder="Pan Limit"
                            slotProps={{
                              input: {
                                readOnly: dialogMode === "view",
                              },
                            }}
                          />
                          <TextField
                            fullWidth
                            label="Tilt Limit"
                            value={`Min: ${selectedProfile.PTZConfiguration.PanTiltLimits.Range.YRange.Min}, Max: ${selectedProfile.PTZConfiguration.PanTiltLimits.Range.YRange.Max}`}
                            placeholder="Tilt Limit"
                            slotProps={{
                              input: {
                                readOnly: dialogMode === "view",
                              },
                            }}
                          />
                          {selectedProfile.PTZConfiguration.ZoomLimits && (
                            <TextField
                              fullWidth
                              label="Zoom Limit"
                              value={`Min: ${selectedProfile.PTZConfiguration.ZoomLimits?.Range.XRange.Min}, Max: ${selectedProfile.PTZConfiguration.ZoomLimits?.Range.XRange.Max}`}
                              placeholder="Zoom Limit"
                              slotProps={{
                                input: {
                                  readOnly: dialogMode === "view",
                                },
                              }}
                            />
                          )}
                        </Stack>
                      )}
                      {(selectedProfile.PTZConfiguration.MoveRamp ||
                        selectedProfile.PTZConfiguration.PresetRamp ||
                        selectedProfile.PTZConfiguration.PresetTourRamp) && (
                        <Stack direction="row" spacing={2} alignItems="center">
                          {selectedProfile.PTZConfiguration.MoveRamp && (
                            <TextField
                              fullWidth
                              label="Move Ramp"
                              value={selectedProfile.PTZConfiguration.MoveRamp}
                              placeholder="Move Ramp"
                              slotProps={{
                                input: {
                                  readOnly: dialogMode === "view",
                                },
                              }}
                            />
                          )}
                          {selectedProfile.PTZConfiguration.PresetRamp && (
                            <TextField
                              fullWidth
                              label="Preset Ramp"
                              value={
                                selectedProfile.PTZConfiguration.PresetRamp
                              }
                              placeholder="Preset Ramp"
                              slotProps={{
                                input: {
                                  readOnly: dialogMode === "view",
                                },
                              }}
                            />
                          )}
                          {selectedProfile.PTZConfiguration.PresetTourRamp && (
                            <TextField
                              fullWidth
                              label="Preset Tour Ramp"
                              value={
                                selectedProfile.PTZConfiguration.PresetTourRamp
                              }
                              placeholder="Preset Tour Ramp"
                              slotProps={{
                                input: {
                                  readOnly: dialogMode === "view",
                                },
                              }}
                            />
                          )}
                        </Stack>
                      )}
                    </Box>
                  </Box>
                )}

                {/* Metadata Configuration */}
                {selectedProfile.MetadataConfiguration && (
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>
                      Metadata Configuration
                    </Typography>
                    <Box
                      sx={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 2,
                        mt: 2,
                      }}
                    >
                      <Stack direction="row" spacing={2} alignItems="center">
                        <TextField
                          fullWidth
                          label="Name"
                          value={selectedProfile.MetadataConfiguration.Name}
                          placeholder="Name"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Use Count"
                          value={selectedProfile.MetadataConfiguration.UseCount}
                          placeholder="Use Count"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                      </Stack>
                      <Stack direction="row" spacing={2} alignItems="center">
                        <TextField
                          fullWidth
                          label="Token"
                          value={selectedProfile.MetadataConfiguration.token}
                          placeholder="Token"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Session Timeout"
                          value={
                            selectedProfile.MetadataConfiguration.SessionTimeout
                          }
                          placeholder="Session Timeout"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                      </Stack>
                      <Stack direction="row" spacing={2} alignItems="center">
                        <TextField
                          fullWidth
                          label="PTZ Status"
                          value={
                            selectedProfile.MetadataConfiguration.PTZStatus
                              .Status
                              ? "Enabled"
                              : "Disabled"
                          }
                          placeholder="PTZ Status"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="PTZ Position"
                          value={
                            selectedProfile.MetadataConfiguration.PTZStatus
                              .Position
                              ? "Enabled"
                              : "Disabled"
                          }
                          placeholder="PTZ Position"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="PTZ Field of View"
                          value={
                            selectedProfile.MetadataConfiguration.PTZStatus
                              .FieldOfView
                              ? "Enabled"
                              : "Disabled"
                          }
                          placeholder="PTZ Field of View"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                      </Stack>
                      <Stack direction="row" spacing={2} alignItems="center">
                        <TextField
                          fullWidth
                          label="Analytics"
                          value={
                            selectedProfile.MetadataConfiguration.Analytics
                              ? "Enabled"
                              : "Disabled"
                          }
                          placeholder="Analytics"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Geo Location"
                          value={
                            selectedProfile.MetadataConfiguration.GeoLocation
                              ? "Enabled"
                              : "Disabled"
                          }
                          placeholder="Geo Location"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Shape Polygon"
                          value={
                            selectedProfile.MetadataConfiguration.ShapePolygon
                              ? "Enabled"
                              : "Disabled"
                          }
                          placeholder="Shape Polygon"
                          slotProps={{
                            input: {
                              readOnly: dialogMode === "view",
                            },
                          }}
                        />
                      </Stack>
                    </Box>
                  </Box>
                )}
              </Box>
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={handleDialogClose}>
              {dialogMode === "add" ? "Cancel" : "Close"}
            </Button>
            {dialogMode === "add" && (
              <Button
                onClick={handleCreateProfile}
                variant="contained"
                disabled={!profileName || createProfileMutation.isPending}
              >
                {createProfileMutation.isPending ? (
                  <CircularProgress enableTrackSlot size={24} />
                ) : (
                  "Add"
                )}
              </Button>
            )}
            {dialogMode === "view" &&
              selectedProfile &&
              !selectedProfile.fixed && (
                <Button
                  onClick={() => handleDeleteProfile(selectedProfile)}
                  color="error"
                  disabled={deleteProfileMutation.isPending}
                >
                  {deleteProfileMutation.isPending ? (
                    <CircularProgress enableTrackSlot size={24} />
                  ) : (
                    "Delete"
                  )}
                </Button>
              )}
          </DialogActions>
        </Dialog>
      </Box>
    </QueryWrapper>
  );
}
