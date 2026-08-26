import { Help, Wikis } from "@carbon/icons-react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useMemo, useState } from "react";

import {
  useGetMediaProfiles,
  useGetMediaSnapshotUri,
  useGetMediaStreamUri,
} from "lib/api/actions/onvif/media";

import { QueryWrapper } from "../../config/QueryWrapper";

interface MediaUriProps {
  cameraIdentifier: string;
  mediaCapabilities?: any;
}

const DEFAULT_STREAM_TYPE = "RTP-Unicast";
const DEFAULT_PROTOCOL = "RTSP";

export function MediaUri({
  cameraIdentifier,
  mediaCapabilities,
}: MediaUriProps) {
  const TITLE = "Media URI";
  const DESC =
    "READ-ONLY: List of media stream URIs for snapshot and stream.";

  // ONVIF API hooks
  const { data, isLoading, isError, error } =
    useGetMediaProfiles(cameraIdentifier);

  const profiles = data?.profiles;
  const [selectedProfile, setSelectedProfile] = useState<any>(null);

  const snapshotSupported = mediaCapabilities?.SnapshotUri !== false;

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);

  const streamParams = useMemo(
    () => ({
      token: selectedProfile?.token,
      stream_type: DEFAULT_STREAM_TYPE,
      protocol: DEFAULT_PROTOCOL,
    }),
    [selectedProfile?.token],
  );

  const {
    data: streamData,
    isLoading: isStreamLoading,
    isError: isStreamError,
    error: streamError,
  } = useGetMediaStreamUri(cameraIdentifier, streamParams, dialogOpen);

  const {
    data: snapshotData,
    isLoading: isSnapshotLoading,
    isError: isSnapshotError,
    error: snapshotError,
  } = useGetMediaSnapshotUri(
    cameraIdentifier,
    selectedProfile?.token,
    dialogOpen && snapshotSupported,
  );

  const handleViewUri = (profile: any) => {
    setSelectedProfile(profile);
    setDialogOpen(true);
  };

  const handleDialogClose = () => {
    setDialogOpen(false);
  };

  const streamUri = streamData?.stream_uri;
  const snapshotUri = snapshotSupported
    ? snapshotData?.snapshot_uri
    : undefined;

  return (
    <QueryWrapper
      isLoading={isLoading}
      isError={isError}
      errorMessage={error?.message || "Failed to load media profiles"}
      isEmpty={profiles?.length === 0}
      emptyMessage="No media profiles available"
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
          <Typography variant="caption" color="text.secondary">
            {DEFAULT_PROTOCOL} • {DEFAULT_STREAM_TYPE}
          </Typography>
        </Box>

        {profiles && profiles.length > 0 && (
          <Box display="flex" flexDirection="column" gap={1}>
            {profiles.map((profile) => (
              <Button
                key={profile.token}
                variant="outlined"
                fullWidth
                onClick={() => handleViewUri(profile)}
                sx={{
                  p: 1.5,
                  display: "flex",
                  justifyContent: "flex-start",
                  textTransform: "none",
                }}
                color="inherit"
              >
                <Wikis size={20} style={{ marginRight: 8, flexShrink: 0 }} />
                <Box
                  sx={{
                    flexGrow: 1,
                    textAlign: "left",
                    overflow: "hidden",
                  }}
                >
                  <Typography variant="body2" sx={{ fontWeight: 500 }}>
                    {profile.Name}
                  </Typography>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ display: "block" }}
                  >
                    {profile.token}
                  </Typography>
                </Box>
                <Box sx={{ flexShrink: 0, textAlign: "right" }}>
                  <Typography variant="caption" color="text.secondary">
                    {snapshotSupported ? "Stream + Snapshot" : "Stream only"}
                  </Typography>
                </Box>
              </Button>
            ))}
          </Box>
        )}

        <Dialog
          open={dialogOpen}
          onClose={handleDialogClose}
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
              <Typography variant="inherit">URI Details</Typography>
              <Typography variant="caption" fontWeight="medium" color="primary">
                {selectedProfile?.Name || selectedProfile?.token}
              </Typography>
            </Box>
          </DialogTitle>
          <DialogContent>
            <Box
              sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}
            >
              <Stack direction="column" spacing={2}>
                <TextField
                  fullWidth
                  label="Profile Name"
                  value={selectedProfile?.Name || ""}
                  slotProps={{
                    input: {
                      readOnly: true,
                    },
                  }}
                />
                <TextField
                  fullWidth
                  label="Profile Token"
                  value={selectedProfile?.token || ""}
                  slotProps={{
                    input: {
                      readOnly: true,
                    },
                  }}
                />
              </Stack>

              <Stack direction="row" spacing={2} alignItems="center">
                <TextField
                  fullWidth
                  label="Protocol"
                  value={DEFAULT_PROTOCOL}
                  slotProps={{
                    input: {
                      readOnly: true,
                    },
                  }}
                />
                <TextField
                  fullWidth
                  label="Stream Type"
                  value={DEFAULT_STREAM_TYPE}
                  slotProps={{
                    input: {
                      readOnly: true,
                    },
                  }}
                />
              </Stack>

              {/* Stream URI Section */}
              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  Stream URI
                </Typography>
                {isStreamLoading && (
                  <Box display="flex" justifyContent="center" py={2}>
                    <CircularProgress enableTrackSlot size={24} />
                  </Box>
                )}
                {isStreamError && !isStreamLoading && (
                  <Alert severity="error" variant="standard" sx={{ border: 0 }}>
                    {streamError?.message || "Failed to load stream URI"}
                  </Alert>
                )}
                {!isStreamLoading && !isStreamError && streamUri && (
                  <Box sx={{ mt: 2 }}>
                    <TextField
                      fullWidth
                      multiline
                      minRows={3}
                      label="URI"
                      value={streamUri.Uri || ""}
                      slotProps={{
                        input: {
                          readOnly: true,
                        },
                      }}
                    />
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
                          label="Invalid After Connect"
                          value={streamUri.InvalidAfterConnect ? "Yes" : "No"}
                          slotProps={{
                            input: {
                              readOnly: true,
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Invalid After Reboot"
                          value={streamUri.InvalidAfterReboot ? "Yes" : "No"}
                          slotProps={{
                            input: {
                              readOnly: true,
                            },
                          }}
                        />
                        <TextField
                          fullWidth
                          label="Timeout"
                          value={streamUri.Timeout || ""}
                          slotProps={{
                            input: {
                              readOnly: true,
                            },
                          }}
                        />
                      </Stack>
                    </Box>
                  </Box>
                )}
              </Box>

              {/* Snapshot URI Section */}
              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  Snapshot URI
                </Typography>
                {snapshotSupported && isSnapshotLoading && (
                  <Box display="flex" justifyContent="center" py={2}>
                    <CircularProgress enableTrackSlot size={24} />
                  </Box>
                )}
                {snapshotSupported && isSnapshotError && !isSnapshotLoading && (
                  <Alert severity="error" variant="standard" sx={{ border: 0 }}>
                    {snapshotError?.message || "Failed to load snapshot URI"}
                  </Alert>
                )}
                {snapshotSupported &&
                  !isSnapshotLoading &&
                  !isSnapshotError &&
                  snapshotUri && (
                    <Box sx={{ mt: 2 }}>
                      <TextField
                        fullWidth
                        multiline
                        minRows={3}
                        label="URI"
                        value={snapshotUri.Uri || ""}
                        slotProps={{
                          input: {
                            readOnly: true,
                          },
                        }}
                      />
                      <Box
                        sx={{
                          display: "flex",
                          flexDirection: "column",
                          gap: 1,
                          mt: 2,
                        }}
                      >
                        <Stack direction="row" spacing={2} alignItems="center">
                          <TextField
                            fullWidth
                            label="Invalid After Connect"
                            value={
                              snapshotUri.InvalidAfterConnect ? "Yes" : "No"
                            }
                            slotProps={{
                              input: {
                                readOnly: true,
                              },
                            }}
                          />
                          <TextField
                            fullWidth
                            label="Invalid After Reboot"
                            value={
                              snapshotUri.InvalidAfterReboot ? "Yes" : "No"
                            }
                            slotProps={{
                              input: {
                                readOnly: true,
                              },
                            }}
                          />
                          <TextField
                            fullWidth
                            label="Timeout"
                            value={snapshotUri.Timeout || ""}
                            slotProps={{
                              input: {
                                readOnly: true,
                              },
                            }}
                          />
                        </Stack>
                      </Box>
                    </Box>
                  )}
                {!snapshotSupported && (
                  <Typography variant="caption" color="text.secondary">
                    Snapshot URI is not supported by this camera.
                  </Typography>
                )}
              </Box>
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleDialogClose}>Close</Button>
          </DialogActions>
        </Dialog>
      </Box>
    </QueryWrapper>
  );
}
