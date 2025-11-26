import { Box, Button, Typography } from "@mui/material";

interface DrawingModeInstructionsProps {
  drawingType: "zone" | "mask" | null;
  drawingPointsCount: number;
  onCompleteDrawing: () => void;
  onCancelDrawing: () => void;
}

export function DrawingModeInstructions({
  drawingType,
  drawingPointsCount,
  onCompleteDrawing,
  onCancelDrawing,
}: DrawingModeInstructionsProps) {
  return (
    <Box
      mb={2}
      p={2}
      sx={{
        bgcolor: "action.hover",
        borderRadius: 1,
      }}
    >
      <Typography variant="caption" display="block" gutterBottom>
        Drawing {drawingType}...
      </Typography>
      <Typography variant="caption" display="block" mb={1}>
        Click on the image to add points. Minimum 3 points required.
      </Typography>
      <Typography variant="caption" display="block" mb={2}>
        Points: {drawingPointsCount}
      </Typography>
      <Box display="flex" gap={1}>
        <Button
          size="small"
          variant="contained"
          onClick={onCompleteDrawing}
          disabled={drawingPointsCount < 3}
          fullWidth
        >
          Complete
        </Button>
        <Button
          size="small"
          variant="outlined"
          onClick={onCancelDrawing}
          fullWidth
        >
          Cancel
        </Button>
      </Box>
    </Box>
  );
}
