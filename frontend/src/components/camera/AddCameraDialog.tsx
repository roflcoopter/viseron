import { Add, Checkmark, Close } from "@carbon/icons-react";
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
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import TextField from "@mui/material/TextField";
import { useState } from "react";

import { LoadingButton } from "components/buttons/LoadingButton";
import {
  AddCameraConfigPayload,
  useAddCameraConfig,
} from "lib/api/cameras";

type AddCameraDialogProps = {
  open: boolean;
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
  { label: "Generic", path: "/", port: 554, stream_format: "rtsp" as const },
];

const identifierFromName = (name: string) =>
  name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .replace(/_+/g, "_");

const initialForm: AddCameraConfigPayload = {
  identifier: "",
  name: "",
  host: "",
  port: 554,
  path: "/Streaming/Channels/101/",
  stream_format: "rtsp",
  username: "",
  password: "",
  substream_path: "",
  substream_port: 554,
  substream_stream_format: "rtsp",
  idle_timeout: 5,
  enable_recorder: true,
  enable_nvr: true,
  reload: true,
};

export function AddCameraDialog({ open, onClose }: AddCameraDialogProps) {
  const [form, setForm] = useState<AddCameraConfigPayload>(initialForm);
  const [identifierEdited, setIdentifierEdited] = useState(false);

  const addCamera = useAddCameraConfig({
    onSuccess: () => {
      setForm(initialForm);
      setIdentifierEdited(false);
      onClose();
    },
  });

  const updateForm = <K extends keyof AddCameraConfigPayload>(
    key: K,
    value: AddCameraConfigPayload[K],
  ) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const close = () => {
    if (!addCamera.isPending) {
      onClose();
    }
  };

  const submit = () => {
    addCamera.mutate({
      ...form,
      identifier: form.identifier.trim(),
      name: form.name.trim(),
      host: form.host.trim(),
      path: form.path.trim(),
      username: form.username?.trim() || null,
      password: form.password || null,
      substream_path: form.substream_path?.trim() || null,
    });
  };

  const valid =
    /^[A-Za-z0-9_]+$/.test(form.identifier) &&
    form.name.trim().length > 0 &&
    form.host.trim().length > 0 &&
    form.path.trim().length > 0;

  return (
    <Dialog open={open} onClose={close} fullWidth maxWidth="md">
      <DialogTitle>Add Camera</DialogTitle>
      <DialogContent>
        <Grid container spacing={2} sx={{ mt: 0.5 }}>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              label="Name"
              value={form.name}
              fullWidth
              autoFocus
              onChange={(event) => {
                const value = event.target.value;
                updateForm("name", value);
                if (!identifierEdited) {
                  updateForm("identifier", identifierFromName(value));
                }
              }}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              label="Identifier"
              value={form.identifier}
              fullWidth
              helperText="Letters, numbers, and underscores"
              error={
                form.identifier.length > 0 &&
                !/^[A-Za-z0-9_]+$/.test(form.identifier)
              }
              onChange={(event) => {
                setIdentifierEdited(true);
                updateForm("identifier", event.target.value);
              }}
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
              <InputLabel id="camera-path-preset-label">Preset</InputLabel>
              <Select
                labelId="camera-path-preset-label"
                label="Preset"
                value={
                  PATH_PRESETS.find(
                    (preset) =>
                      preset.path === form.path &&
                      preset.port === form.port &&
                      preset.stream_format === form.stream_format,
                  )?.label || ""
                }
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
          <Grid size={{ xs: 12, md: 6 }}>
            <FormControl fullWidth>
              <InputLabel id="camera-stream-format-label">
                Stream format
              </InputLabel>
              <Select
                labelId="camera-stream-format-label"
                label="Stream format"
                value={form.stream_format}
                onChange={(event) =>
                  updateForm(
                    "stream_format",
                    event.target.value as AddCameraConfigPayload["stream_format"],
                  )
                }
              >
                <MenuItem value="rtsp">RTSP</MenuItem>
                <MenuItem value="mjpeg">MJPEG / HTTP</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              label="Username"
              value={form.username}
              fullWidth
              onChange={(event) => updateForm("username", event.target.value)}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              label="Password"
              type="password"
              value={form.password}
              fullWidth
              onChange={(event) => updateForm("password", event.target.value)}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 8 }}>
            <TextField
              label="Substream Path"
              value={form.substream_path}
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
              value={form.substream_port}
              fullWidth
              slotProps={{ htmlInput: { min: 1, max: 65535 } }}
              onChange={(event) =>
                updateForm("substream_port", Number(event.target.value))
              }
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
        </Grid>
      </DialogContent>
      <DialogActions>
        <Button startIcon={<Close />} onClick={close}>
          Cancel
        </Button>
        <LoadingButton
          icon={addCamera.isSuccess ? <Checkmark /> : <Add />}
          text="Add Camera"
          state={
            addCamera.isPending
              ? "loading"
              : addCamera.isError
                ? "error"
                : addCamera.isSuccess
                  ? "success"
                  : "normal"
          }
          variant="contained"
          onClick={valid ? submit : undefined}
        />
      </DialogActions>
    </Dialog>
  );
}
