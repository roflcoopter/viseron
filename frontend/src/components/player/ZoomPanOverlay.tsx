import { Box, Typography } from "@mui/material";

interface ZoomPanOverlayProps {
  scale: number;
  translateX: number;
  translateY: number;
  isVisible: boolean;
}

export function ZoomPanOverlay({
  scale,
  translateX,
  translateY,
  isVisible,
}: ZoomPanOverlayProps) {
  if (!isVisible || scale === 1.0) {
    return null;
  }

  return (
    <Box
      sx={{
        position: "absolute",
        bottom: 8,
        left: 8,
        backgroundColor: "rgba(0, 0, 0, 0.7)",
        color: "white",
        padding: "4px 8px",
        borderRadius: 1,
        fontSize: "0.75rem",
        fontFamily: "monospace",
        zIndex: 1000,
        pointerEvents: "none",
        minWidth: "90px",
      }}
    >
      <Typography variant="caption" component="div" sx={{ lineHeight: 1.2 }}>
        Zoom: {scale.toFixed(1)}x
      </Typography>
      <Typography variant="caption" component="div" sx={{ lineHeight: 1.2 }}>
        X: {Math.round(translateX)}px
      </Typography>
      <Typography variant="caption" component="div" sx={{ lineHeight: 1.2 }}>
        Y: {Math.round(translateY)}px
      </Typography>
    </Box>
  );
}