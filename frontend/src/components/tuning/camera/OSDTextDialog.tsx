import {
  AlignBoxBottomLeft,
  AlignBoxBottomRight,
  AlignBoxTopLeft,
  AlignBoxTopRight,
  Camera,
  Information,
  Label,
  TextSubscript,
  Time,
  Video,
} from "@carbon/icons-react";
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  Radio,
  RadioGroup,
  Slider,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import Stack from "@mui/material/Stack";
import { useTheme } from "@mui/material/styles";
import { useEffect, useState } from "react";

interface TuneOSDTextDialogProps {
  open: boolean;
  isEdit: boolean;
  osdType: "camera" | "recorder";
  textType: "timestamp" | "custom" | "text";
  customText: string;
  position: "top-left" | "top-right" | "bottom-left" | "bottom-right";
  paddingX: number;
  paddingY: number;
  fontSize: number;
  fontColorHex: string;
  boxColorHex: string;
  boxOpacity: number;
  onOSDTypeChange: (type: "camera" | "recorder") => void;
  onTextTypeChange: (type: "timestamp" | "custom" | "text") => void;
  onCustomTextChange: (text: string) => void;
  onPositionChange: (
    position: "top-left" | "top-right" | "bottom-left" | "bottom-right",
  ) => void;
  onPaddingXChange: (value: number) => void;
  onPaddingYChange: (value: number) => void;
  onFontSizeChange: (value: number) => void;
  onFontColorChange: (value: string) => void;
  onBoxColorChange: (value: string) => void;
  onBoxOpacityChange: (value: number) => void;
  onConfirm: () => void;
  onCancel: () => void;
}

const positions: Array<{
  value: "top-left" | "top-right" | "bottom-left" | "bottom-right";
  label: string;
  icon: React.ComponentType<{ size?: number }>;
}> = [
  { value: "top-left", label: "Top Left", icon: AlignBoxTopLeft },
  { value: "top-right", label: "Top Right", icon: AlignBoxTopRight },
  { value: "bottom-left", label: "Bottom Left", icon: AlignBoxBottomLeft },
  { value: "bottom-right", label: "Bottom Right", icon: AlignBoxBottomRight },
];

export function TuneOSDTextDialog({
  open,
  isEdit,
  osdType,
  textType,
  customText,
  position,
  paddingX,
  paddingY,
  fontSize,
  fontColorHex,
  boxColorHex,
  boxOpacity,
  onOSDTypeChange,
  onTextTypeChange,
  onCustomTextChange,
  onPositionChange,
  onPaddingXChange,
  onPaddingYChange,
  onFontSizeChange,
  onFontColorChange,
  onBoxColorChange,
  onBoxOpacityChange,
  onConfirm,
  onCancel,
}: TuneOSDTextDialogProps) {
  const [localCustomText, setLocalCustomText] = useState(customText);
  const theme = useTheme();

  useEffect(() => {
    setLocalCustomText(customText);
  }, [customText]);

  const handleCustomTextChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setLocalCustomText(e.target.value);
    onCustomTextChange(e.target.value);
  };

  return (
    <Dialog open={open} onClose={onCancel} maxWidth="sm" fullWidth>
      <DialogTitle>
        {isEdit ? "Edit" : "Add"} OSD (On-Screen Display) Text
      </DialogTitle>
      <DialogContent sx={{ overflowX: "hidden", overflowY: "auto" }}>
        <Box display="flex" flexDirection="column" gap={3} pt={1}>
          {/* OSD Type Selection */}
          <FormControl>
            <Typography variant="subtitle2" gutterBottom>
              Apply To
            </Typography>
            <ToggleButtonGroup
              value={osdType}
              exclusive
              onChange={(_, value) => value && onOSDTypeChange(value)}
              fullWidth
            >
              <ToggleButton value="camera">
                <Camera size={20} style={{ marginRight: 8 }} />
                Camera
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
                  {osdType === "camera"
                    ? "Camera: Shown on frames, snapshots, thumbnails, etc."
                    : "Recorder: Shown on recordings only."}
                </Typography>
              </Stack>
            </Box>
          </FormControl>

          {/* Text Type Selection */}
          <FormControl>
            <Typography variant="subtitle2" gutterBottom>
              Content
            </Typography>
            <RadioGroup
              value={textType}
              onChange={(e) =>
                onTextTypeChange(
                  e.target.value as "timestamp" | "custom" | "text",
                )
              }
            >
              <FormControlLabel
                value="timestamp"
                control={<Radio />}
                label={
                  <Box display="flex" alignItems="center" gap={1}>
                    <Time size={16} />
                    <Typography variant="body2">Timestamp</Typography>
                  </Box>
                }
              />
              <FormControlLabel
                value="custom"
                control={<Radio />}
                label={
                  <Box display="flex" alignItems="center" gap={1}>
                    <TextSubscript size={16} />
                    <Typography variant="body2">
                      Custom Text with Timestamp
                    </Typography>
                  </Box>
                }
              />
              <FormControlLabel
                value="text"
                control={<Radio />}
                label={
                  <Box display="flex" alignItems="center" gap={1}>
                    <Label size={16} />
                    <Typography variant="body2">
                      Text Only (No Timestamp)
                    </Typography>
                  </Box>
                }
              />
            </RadioGroup>
          </FormControl>

          {/* Custom Text Input */}
          {(textType === "custom" || textType === "text") && (
            <TextField
              label="Custom Text"
              value={localCustomText}
              onChange={handleCustomTextChange}
              placeholder="Enter custom text"
              helperText={
                textType === "custom"
                  ? "Timestamp will be appended automatically"
                  : "Text without timestamp"
              }
              fullWidth
            />
          )}

          {/* Position Selection */}
          <FormControl>
            <Typography variant="subtitle2" gutterBottom>
              Position
            </Typography>
            <Box display="grid" gridTemplateColumns="1fr 1fr" gap={1}>
              {positions.map((pos) => {
                const IconComponent = pos.icon;
                return (
                  <Button
                    key={pos.value}
                    variant={position === pos.value ? "contained" : "outlined"}
                    onClick={() => onPositionChange(pos.value)}
                    fullWidth
                    startIcon={<IconComponent size={20} />}
                  >
                    {pos.label}
                  </Button>
                );
              })}
            </Box>
          </FormControl>

          {/* Padding X Slider */}
          <FormControl>
            <Typography variant="subtitle2" gutterBottom>
              Horizontal Padding: {paddingX}px
            </Typography>
            <Slider
              value={paddingX}
              onChange={(_, value) => onPaddingXChange(value as number)}
              min={0}
              max={100}
              step={1}
              valueLabelDisplay="auto"
            />
          </FormControl>

          {/* Padding Y Slider */}
          <FormControl>
            <Typography variant="subtitle2" gutterBottom>
              Vertical Padding: {paddingY}px
            </Typography>
            <Slider
              value={paddingY}
              onChange={(_, value) => onPaddingYChange(value as number)}
              min={0}
              max={100}
              step={1}
              valueLabelDisplay="auto"
            />
          </FormControl>

          {/* Font Size Slider */}
          <FormControl>
            <Typography variant="subtitle2" gutterBottom>
              Font Size: {fontSize}px
            </Typography>
            <Slider
              value={fontSize}
              onChange={(_, value) => onFontSizeChange(value as number)}
              min={12}
              max={60}
              step={2}
              valueLabelDisplay="auto"
            />
          </FormControl>

          {/* Font Color Picker */}
          <FormControl>
            <Typography variant="subtitle2" gutterBottom>
              Font Color
            </Typography>
            <Box display="flex" gap={2} alignItems="center">
              <input
                type="color"
                value={fontColorHex}
                onChange={(e) => onFontColorChange(e.target.value)}
                style={{
                  width: "60px",
                  height: "40px",
                  border: "none",
                  borderRadius: "4px",
                  cursor: "pointer",
                }}
              />
              <TextField
                value={fontColorHex}
                onChange={(e) => onFontColorChange(e.target.value)}
                placeholder="#ffffff"
                size="small"
                sx={{ flex: 1 }}
              />
            </Box>
          </FormControl>

          {/* Box Color Picker */}
          <FormControl>
            <Typography variant="subtitle2" gutterBottom>
              Box Color
            </Typography>
            <Box display="flex" gap={2} alignItems="center">
              <input
                type="color"
                value={boxColorHex}
                onChange={(e) => onBoxColorChange(e.target.value)}
                style={{
                  width: "60px",
                  height: "40px",
                  border: "none",
                  borderRadius: "4px",
                  cursor: "pointer",
                }}
              />
              <TextField
                value={boxColorHex}
                onChange={(e) => onBoxColorChange(e.target.value)}
                placeholder="#000000"
                size="small"
                sx={{ flex: 1 }}
              />
            </Box>
          </FormControl>

          {/* Box Opacity Slider */}
          <FormControl>
            <Typography variant="subtitle2" gutterBottom>
              Box Opacity: {(boxOpacity * 100).toFixed(0)}%
            </Typography>
            <Slider
              value={boxOpacity}
              onChange={(_, value) => onBoxOpacityChange(value as number)}
              min={0}
              max={1}
              step={0.05}
              valueLabelDisplay="auto"
              valueLabelFormat={(value) => `${(value * 100).toFixed(0)}%`}
            />
          </FormControl>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel}>Cancel</Button>
        <Button onClick={onConfirm} variant="contained" color="primary">
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}
