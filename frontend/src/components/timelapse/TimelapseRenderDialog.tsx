import { VideoAdd } from "@carbon/icons-react";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import LinearProgress from "@mui/material/LinearProgress";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useState } from "react";

import {
  DEFAULT_FPS,
  FPS_OPTIONS,
  MAX_RENDER_FRAMES,
  RENDER_WIDTHS,
  formatDuration,
  formatTimestamp,
} from "components/timelapse/utils";
import {
  RenderTimelapseState,
  isRenderActive,
  useRenderTimelapse,
} from "hooks/UseRenderTimelapse";

// Target video lengths in seconds, 0 uses every frame
const DURATION_OPTIONS = [10, 30, 60, 120, 300, 0];
const DEFAULT_DURATION = 60;

export function estimateFrames(total: number, fps: number, duration: number) {
  const target = duration === 0 ? total : fps * duration;
  return Math.max(Math.min(total, target, MAX_RENDER_FRAMES), 0);
}

function statusText(state: RenderTimelapseState) {
  switch (state.status) {
    case "starting":
      return "Starting...";
    case "queued":
      return "Waiting for other renders to finish...";
    case "rendering":
      return `Rendering frame ${state.frame} of ${state.total_frames}`;
    case "encoding":
      return "Encoding video...";
    case "downloading":
      return "Downloading...";
    default:
      return "";
  }
}

function RenderProgress({ state }: { state: RenderTimelapseState }) {
  return (
    <Stack spacing={1}>
      <Typography variant="body2">{statusText(state)}</Typography>
      <LinearProgress
        variant={state.status === "rendering" ? "determinate" : "indeterminate"}
        value={state.status === "rendering" ? state.progress : undefined}
      />
    </Stack>
  );
}

type TimelapseRenderDialogProps = {
  open: boolean;
  onClose: () => void;
  camera_identifier: string;
  start: number;
  end: number;
  total: number;
  render: ReturnType<typeof useRenderTimelapse>;
};

export function TimelapseRenderDialog({
  open,
  onClose,
  camera_identifier,
  start,
  end,
  total,
  render,
}: TimelapseRenderDialogProps) {
  const [fps, setFps] = useState(DEFAULT_FPS);
  const [duration, setDuration] = useState(DEFAULT_DURATION);
  const [width, setWidth] = useState(0);
  const { state } = render;
  const active = isRenderActive(state);
  const frames = estimateFrames(total, fps, duration);

  const hide = () => {
    render.hide();
    onClose();
  };

  const close = () => {
    if (active) {
      hide();
      return;
    }
    render.reset();
    onClose();
  };

  const startRender = () => {
    render.start({
      camera_identifier,
      start,
      end,
      fps,
      max_frames: Math.max(frames, 1),
      max_width: width || null,
    });
  };

  let content: React.ReactNode;
  let actions: React.ReactNode;
  if (active) {
    content = <RenderProgress state={state} />;
    actions = (
      <>
        <Button onClick={hide}>Hide</Button>
        <Button
          color="error"
          onClick={() => render.cancel()}
          disabled={state.status === "downloading"}
        >
          Cancel
        </Button>
      </>
    );
  } else if (state.status === "done") {
    content = (
      <Alert severity="success">The timelapse has been downloaded.</Alert>
    );
    actions = <Button onClick={close}>Close</Button>;
  } else {
    content = (
      <Stack spacing={3} sx={{ mt: 1 }}>
        {state.status === "error" ? (
          <Alert severity="error">{state.error}</Alert>
        ) : null}
        {state.status === "cancelled" ? (
          <Alert severity="info">The render was cancelled.</Alert>
        ) : null}
        <Typography variant="body2" color="text.secondary">
          {formatTimestamp(start, false)} – {formatTimestamp(end, false)}
        </Typography>
        <TextField
          select
          label="Frame rate"
          value={fps}
          onChange={(event) => setFps(Number(event.target.value))}
        >
          {FPS_OPTIONS.map((option) => (
            <MenuItem key={option} value={option}>
              {option} fps
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          label="Video length"
          value={duration}
          onChange={(event) => setDuration(Number(event.target.value))}
        >
          {DURATION_OPTIONS.map((option) => (
            <MenuItem key={option} value={option}>
              {option === 0 ? "All frames" : formatDuration(option)}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          label="Resolution"
          value={width}
          onChange={(event) => setWidth(Number(event.target.value))}
        >
          <MenuItem value={0}>Original</MenuItem>
          {RENDER_WIDTHS.map((option) => (
            <MenuItem key={option.width} value={option.width}>
              {option.label} ({option.width} px wide)
            </MenuItem>
          ))}
        </TextField>
        <Typography variant="body2" data-testid="render-estimate">
          {frames > 0
            ? `About ${frames} frames, ${formatDuration(frames / fps)} of video`
            : "There are no frames in this range"}
        </Typography>
      </Stack>
    );
    actions = (
      <>
        <Button onClick={close}>Close</Button>
        <Button
          variant="contained"
          onClick={startRender}
          disabled={frames === 0}
        >
          Render
        </Button>
      </>
    );
  }

  return (
    <Dialog fullWidth maxWidth="xs" open={open} onClose={close}>
      <DialogTitle>
        <Stack direction="row" alignItems="center" spacing={1}>
          <VideoAdd size={24} />
          <Typography variant="h6">Render Timelapse</Typography>
        </Stack>
      </DialogTitle>
      <DialogContent>{content}</DialogContent>
      <DialogActions>{actions}</DialogActions>
    </Dialog>
  );
}
