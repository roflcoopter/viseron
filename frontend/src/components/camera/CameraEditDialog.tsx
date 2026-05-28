import { Checkmark, Close, Save, TrashCan } from "@carbon/icons-react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import FormControl from "@mui/material/FormControl";
import FormControlLabel from "@mui/material/FormControlLabel";
import Grid from "@mui/material/Grid";
import InputLabel from "@mui/material/InputLabel";
import ListItemText from "@mui/material/ListItemText";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useEffect, useMemo, useState } from "react";

import { LoadingButton } from "components/buttons/LoadingButton";
import { ErrorMessage } from "components/error/ErrorMessage";
import { Loading } from "components/loading/Loading";
import {
  useCameraAccessConfig,
  useSaveCameraAccessConfig,
} from "lib/api/cameraAccess";
import {
  CameraConfigPayload,
  useCameraConfig,
  useDeleteCameraConfig,
  useUpdateCameraConfig,
} from "lib/api/cameras";
import * as types from "lib/types";

type CameraEditDialogProps = {
  camera: types.Camera | types.FailedCamera;
  onClose: () => void;
};

const PATH_PRESETS = [
  {
    label: "Mobotix HTTP live",
    path: "/control/faststream.jpg?stream=full&fps=10",
    port: 80,
    stream_format: "mjpeg" as const,
  },
  {
    label: "Mobotix snapshot",
    path: "/record/current.jpg",
    port: 80,
    stream_format: "mjpeg" as const,
  },
  {
    label: "Hikvision main",
    path: "/Streaming/Channels/101/",
    port: 554,
    stream_format: "rtsp" as const,
  },
  {
    label: "Hikvision sub",
    path: "/Streaming/Channels/102/",
    port: 554,
    stream_format: "rtsp" as const,
  },
  {
    label: "Dahua main",
    path: "/cam/realmonitor?channel=1&subtype=0",
    port: 554,
    stream_format: "rtsp" as const,
  },
  {
    label: "Dahua sub",
    path: "/cam/realmonitor?channel=1&subtype=1",
    port: 554,
    stream_format: "rtsp" as const,
  },
];

const EMPTY_FORM: CameraConfigPayload = {
  name: "",
  host: "",
  port: 554,
  path: "",
  stream_format: "rtsp",
  username: "",
  password: "",
  substream_path: "",
  substream_port: 554,
  substream_stream_format: "rtsp",
  fps: null,
  idle_timeout: 5,
  enable_recorder: true,
  enable_nvr: true,
  record_only: false,
  width: null,
  height: null,
  video_filters: [],
  reload: true,
};

function videoFiltersToText(videoFilters: string[] | undefined) {
  return (videoFilters || []).join("\n");
}

function textToVideoFilters(value: string) {
  return value
    .split("\n")
    .map((videoFilter) => videoFilter.trim())
    .filter(Boolean);
}

function numberOrNull(value: string) {
  if (value.trim() === "") {
    return null;
  }
  return Number(value);
}

function updateCameraGroups(
  config: types.CameraAccessConfig,
  cameraIdentifier: string,
  selectedGroupIds: string[],
) {
  const selected = new Set(selectedGroupIds);
  return {
    ...config,
    camera_groups: config.camera_groups.map((group) => {
      const cameras = new Set(group.cameras);
      if (selected.has(group.id)) {
        cameras.add(cameraIdentifier);
      } else {
        cameras.delete(cameraIdentifier);
      }
      return { ...group, cameras: Array.from(cameras).sort() };
    }),
  };
}

export function CameraEditDialog({ camera, onClose }: CameraEditDialogProps) {
  const cameraConfig = useCameraConfig(camera.identifier);
  const cameraAccessConfig = useCameraAccessConfig();
  const updateCameraConfig = useUpdateCameraConfig();
  const deleteCameraConfig = useDeleteCameraConfig();
  const saveCameraAccessConfig = useSaveCameraAccessConfig();
  const [form, setForm] = useState<CameraConfigPayload>(EMPTY_FORM);
  const [selectedGroupIds, setSelectedGroupIds] = useState<string[]>([]);
  const [videoFiltersText, setVideoFiltersText] = useState("");
  const cameraGroups = cameraAccessConfig.data?.config.camera_groups || [];

  useEffect(() => {
    if (!cameraConfig.data?.config) {
      return;
    }
    const {
      identifier: _identifier,
      password_set: _passwordSet,
      ...config
    } = cameraConfig.data.config;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setForm({
      ...EMPTY_FORM,
      ...config,
      password: "",
    });
    setVideoFiltersText(videoFiltersToText(config.video_filters));
  }, [cameraConfig.data]);

  useEffect(() => {
    if (!cameraAccessConfig.data?.config) {
      return;
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSelectedGroupIds(
      cameraAccessConfig.data.config.camera_groups
        .filter((group) => group.cameras.includes(camera.identifier))
        .map((group) => group.id),
    );
  }, [camera.identifier, cameraAccessConfig.data]);

  const updateForm = <K extends keyof CameraConfigPayload>(
    key: K,
    value: CameraConfigPayload[K],
  ) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const selectedPreset = useMemo(
    () =>
      PATH_PRESETS.find(
        (preset) =>
          preset.path === form.path &&
          preset.port === form.port &&
          preset.stream_format === form.stream_format,
      )?.label || "",
    [form.path, form.port, form.stream_format],
  );

  const valid =
    form.name.trim().length > 0 &&
    form.host.trim().length > 0 &&
    form.path.trim().length > 0 &&
    form.port >= 1 &&
    form.port <= 65535;

  const isSaving =
    updateCameraConfig.isPending ||
    saveCameraAccessConfig.isPending ||
    deleteCameraConfig.isPending;

  const save = async () => {
    const payload: CameraConfigPayload = {
      ...form,
      name: form.name.trim(),
      host: form.host.trim(),
      path: form.path.trim(),
      username: form.username?.trim() || null,
      password: form.password || null,
      substream_path: form.substream_path?.trim() || null,
      video_filters: textToVideoFilters(videoFiltersText),
    };

    await updateCameraConfig.mutateAsync({
      cameraIdentifier: camera.identifier,
      payload,
    });

    if (cameraAccessConfig.data?.config) {
      await saveCameraAccessConfig.mutateAsync(
        updateCameraGroups(
          cameraAccessConfig.data.config,
          camera.identifier,
          selectedGroupIds,
        ),
      );
    }

    onClose();
  };

  const deleteCamera = async () => {
    // eslint-disable-next-line no-alert
    if (!window.confirm(`Delete camera ${camera.name}?`)) {
      return;
    }
    await deleteCameraConfig.mutateAsync({
      cameraIdentifier: camera.identifier,
      reload: form.reload,
    });
    onClose();
  };

  const close = () => {
    if (!isSaving) {
      onClose();
    }
  };

  if (cameraConfig.isLoading) {
    return (
      <Dialog open onClose={close} fullWidth maxWidth="md">
        <DialogContent>
          <Loading text="Loading camera" />
        </DialogContent>
      </Dialog>
    );
  }

  if (cameraConfig.isError || !cameraConfig.data) {
    return (
      <Dialog open onClose={close} fullWidth maxWidth="sm">
        <DialogContent>
          <ErrorMessage
            text="Error loading camera"
            subtext={cameraConfig.error?.message}
          />
        </DialogContent>
        <DialogActions>
          <Button startIcon={<Close />} onClick={close}>
            Close
          </Button>
        </DialogActions>
      </Dialog>
    );
  }

  return (
    <Dialog open onClose={close} fullWidth maxWidth="md">
      <DialogTitle>{camera.name}</DialogTitle>
      <DialogContent>
        <Grid container spacing={2} sx={{ mt: 0.5 }}>
          <Grid size={{ xs: 12, md: 7 }}>
            <TextField
              label="Name"
              value={form.name}
              fullWidth
              autoFocus
              onChange={(event) => updateForm("name", event.target.value)}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 5 }}>
            <TextField
              label="Identifier"
              value={camera.identifier}
              fullWidth
              disabled
            />
          </Grid>
          <Grid size={{ xs: 12, md: 8 }}>
            <TextField
              label="Host"
              value={form.host}
              fullWidth
              onChange={(event) => updateForm("host", event.target.value)}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 4 }}>
            <TextField
              label="Port"
              type="number"
              value={form.port}
              fullWidth
              slotProps={{ htmlInput: { min: 1, max: 65535 } }}
              onChange={(event) =>
                updateForm("port", Number(event.target.value))
              }
            />
          </Grid>
          <Grid size={{ xs: 12, md: 5 }}>
            <FormControl fullWidth>
              <InputLabel id="edit-camera-path-preset-label">Preset</InputLabel>
              <Select
                labelId="edit-camera-path-preset-label"
                label="Preset"
                value={selectedPreset}
                onChange={(event) => {
                  const preset = PATH_PRESETS.find(
                    (item) => item.label === event.target.value,
                  );
                  if (!preset) {
                    return;
                  }
                  updateForm("path", preset.path);
                  updateForm("port", preset.port);
                  updateForm("stream_format", preset.stream_format);
                }}
              >
                {PATH_PRESETS.map((preset) => (
                  <MenuItem key={preset.label} value={preset.label}>
                    {preset.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, md: 7 }}>
            <TextField
              label="Path"
              value={form.path}
              fullWidth
              onChange={(event) => updateForm("path", event.target.value)}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 4 }}>
            <FormControl fullWidth>
              <InputLabel id="edit-camera-stream-format-label">
                Stream format
              </InputLabel>
              <Select
                labelId="edit-camera-stream-format-label"
                label="Stream format"
                value={form.stream_format}
                onChange={(event) =>
                  updateForm(
                    "stream_format",
                    event.target.value as CameraConfigPayload["stream_format"],
                  )
                }
              >
                <MenuItem value="rtsp">RTSP</MenuItem>
                <MenuItem value="mjpeg">MJPEG / HTTP</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, md: 4 }}>
            <TextField
              label="FPS"
              type="number"
              value={form.fps ?? ""}
              fullWidth
              slotProps={{ htmlInput: { min: 1 } }}
              onChange={(event) =>
                updateForm("fps", numberOrNull(event.target.value))
              }
            />
          </Grid>
          <Grid size={{ xs: 12, md: 4 }}>
            <TextField
              label="Idle timeout"
              type="number"
              value={form.idle_timeout}
              fullWidth
              slotProps={{ htmlInput: { min: 0 } }}
              onChange={(event) =>
                updateForm("idle_timeout", Number(event.target.value))
              }
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              label="Username"
              value={form.username || ""}
              fullWidth
              onChange={(event) => updateForm("username", event.target.value)}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              label="Password"
              type="password"
              value={form.password || ""}
              placeholder={
                cameraConfig.data.config.password_set ? "Already saved" : ""
              }
              fullWidth
              onChange={(event) => updateForm("password", event.target.value)}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 8 }}>
            <TextField
              label="Substream Path"
              value={form.substream_path || ""}
              fullWidth
              onChange={(event) =>
                updateForm("substream_path", event.target.value)
              }
            />
          </Grid>
          <Grid size={{ xs: 12, md: 4 }}>
            <TextField
              label="Substream Port"
              type="number"
              value={form.substream_port || 554}
              fullWidth
              slotProps={{ htmlInput: { min: 1, max: 65535 } }}
              onChange={(event) =>
                updateForm("substream_port", Number(event.target.value))
              }
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              label="Width"
              type="number"
              value={form.width ?? ""}
              fullWidth
              slotProps={{ htmlInput: { min: 1 } }}
              onChange={(event) =>
                updateForm("width", numberOrNull(event.target.value))
              }
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              label="Height"
              type="number"
              value={form.height ?? ""}
              fullWidth
              slotProps={{ htmlInput: { min: 1 } }}
              onChange={(event) =>
                updateForm("height", numberOrNull(event.target.value))
              }
            />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <TextField
              label="Video filters"
              value={videoFiltersText}
              fullWidth
              multiline
              minRows={2}
              onChange={(event) => setVideoFiltersText(event.target.value)}
            />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 2 }}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={form.enable_recorder}
                    onChange={(event) =>
                      updateForm("enable_recorder", event.target.checked)
                    }
                  />
                }
                label="Recorder"
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={form.enable_nvr}
                    onChange={(event) =>
                      updateForm("enable_nvr", event.target.checked)
                    }
                  />
                }
                label="NVR"
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={Boolean(form.record_only)}
                    onChange={(event) =>
                      updateForm("record_only", event.target.checked)
                    }
                  />
                }
                label="Record only"
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={form.reload}
                    onChange={(event) =>
                      updateForm("reload", event.target.checked)
                    }
                  />
                }
                label="Reload"
              />
            </Box>
          </Grid>

          <Grid size={{ xs: 12 }}>
            <Typography variant="subtitle1" sx={{ mb: 1 }}>
              Camera groups
            </Typography>
            {cameraAccessConfig.isError && (
              <Alert severity="warning">
                Camera group assignments could not be loaded.
              </Alert>
            )}
            {!cameraAccessConfig.isError && cameraGroups.length === 0 && (
              <Alert severity="info">No camera groups configured.</Alert>
            )}
            {!cameraAccessConfig.isError && cameraGroups.length > 0 && (
              <FormControl fullWidth>
                <InputLabel id="camera-groups-label">Groups</InputLabel>
                <Select
                  multiple
                  labelId="camera-groups-label"
                  label="Groups"
                  value={selectedGroupIds}
                  onChange={(event) =>
                    setSelectedGroupIds(
                      typeof event.target.value === "string"
                        ? event.target.value.split(",")
                        : event.target.value,
                    )
                  }
                  renderValue={(selected) =>
                    (selected as string[])
                      .map(
                        (groupId) =>
                          cameraGroups.find((group) => group.id === groupId)
                            ?.name || groupId,
                      )
                      .join(", ")
                  }
                >
                  {cameraGroups.map((group) => (
                    <MenuItem key={group.id} value={group.id}>
                      <Checkbox checked={selectedGroupIds.includes(group.id)} />
                      <ListItemText primary={group.name} secondary={group.id} />
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions>
        <Button
          color="error"
          startIcon={<TrashCan />}
          disabled={isSaving}
          onClick={deleteCamera}
        >
          Delete
        </Button>
        <Box sx={{ flexGrow: 1 }} />
        <Button startIcon={<Close />} onClick={close} disabled={isSaving}>
          Cancel
        </Button>
        <LoadingButton
          icon={updateCameraConfig.isSuccess ? <Checkmark /> : <Save />}
          text="Save"
          state={
            isSaving
              ? "loading"
              : updateCameraConfig.isError || saveCameraAccessConfig.isError
                ? "error"
                : updateCameraConfig.isSuccess
                  ? "success"
                  : "normal"
          }
          variant="contained"
          onClick={valid ? save : undefined}
        />
      </DialogActions>
    </Dialog>
  );
}
