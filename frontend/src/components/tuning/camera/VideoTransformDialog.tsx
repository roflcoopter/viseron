import { Camera, Information, Video } from "@carbon/icons-react";
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import Stack from "@mui/material/Stack";
import { useTheme } from "@mui/material/styles";

import { VideoTransformTarget, VideoTransformType } from "./types";

interface VideoTransformDialogProps {
  open: boolean;
  isEdit: boolean;
  transformTarget: VideoTransformTarget;
  transformType: VideoTransformType;
  onTransformTargetChange: (target: VideoTransformTarget) => void;
  onTransformTypeChange: (type: VideoTransformType) => void;
  onConfirm: () => void;
  onCancel: () => void;
}

export function VideoTransformDialog({
  open,
  isEdit,
  transformTarget,
  transformType,
  onTransformTargetChange,
  onTransformTypeChange,
  onConfirm,
  onCancel,
}: VideoTransformDialogProps) {
  const theme = useTheme();
  return (
    <Dialog open={open} onClose={onCancel} maxWidth="sm" fullWidth>
      <DialogTitle>{isEdit ? "Edit" : "Add"} Video Transform</DialogTitle>
      <DialogContent>
        <Typography variant="subtitle2" gutterBottom>
          Apply To
        </Typography>
        <ToggleButtonGroup
          value={transformTarget}
          exclusive
          onChange={(_, newValue) => {
            if (newValue !== null) {
              onTransformTargetChange(newValue);
            }
          }}
          fullWidth
        >
          <ToggleButton value="camera">
            <Camera size={20} style={{ marginRight: 8 }} /> Camera
          </ToggleButton>
          <ToggleButton value="recorder">
            <Video size={20} style={{ marginRight: 8 }} />
            Recorder
          </ToggleButton>
        </ToggleButtonGroup>
        <Box
          sx={{
            p: 2,
            marginTop: 1,
            marginBottom: 2,
            backgroundColor: theme.palette.action.selected,
            borderRadius: 1,
          }}
        >
          <Stack direction="row" alignItems="flex-start" spacing={1}>
            <Information
              size={16}
              style={{ marginTop: "2px", flexShrink: 0 }}
            />
            <Typography variant="body2">
              {transformTarget === "camera"
                ? "Camera: Transform will be applied to frames, snapshots, thumbnails, etc."
                : "Recorder: Transform will be applied to recordings only."}
            </Typography>
          </Stack>
        </Box>
        {/* Transform Type */}
        <FormControl fullWidth sx={{ mt: 2 }}>
          <InputLabel>Transform Type</InputLabel>
          <Select
            value={transformType}
            label="Transform Type"
            onChange={(e) =>
              onTransformTypeChange(e.target.value as VideoTransformType)
            }
          >
            <MenuItem value="hflip">Horizontal Flip (Mirror)</MenuItem>
            <MenuItem value="vflip">Vertical Flip (Upside Down)</MenuItem>
            <MenuItem value="rotate180">Rotate 180°</MenuItem>
          </Select>
        </FormControl>

        <Typography variant="caption" display="block" sx={{ mt: 1 }}>
          {transformType === "hflip" && "Flips video horizontally (left-right)"}
          {transformType === "vflip" && "Flips video vertically (top-bottom)"}
          {transformType === "rotate180" && "Rotates video 180 degrees"}
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel}>Cancel</Button>
        <Button onClick={onConfirm} variant="contained">
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}
