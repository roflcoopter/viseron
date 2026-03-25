import { VideoOff } from "@carbon/icons-react";
import Box from "@mui/material/Box";
import { useTheme } from "@mui/material/styles";

interface HlsErrorOverlayProps {
  error: string | null | undefined;
}

export function HlsErrorOverlay({ error }: HlsErrorOverlayProps) {
  const theme = useTheme();

  if (!error) {
    return null;
  }

  return (
    <Box
      sx={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        width: "100%",
        height: "100%",
        backgroundColor: (t) =>
          t.palette.mode === "dark"
            ? "rgba(0, 0, 0, 0.8)"
            : "rgba(235, 235, 235, 0.8)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: 200,
        gap: 2,
        zIndex: 2,
      }}
    >
      <VideoOff
        size={48}
        style={{
          color: theme.palette.text.secondary,
          opacity: 0.5,
        }}
      />
      <Box
        sx={{
          color: theme.palette.text.secondary,
          textAlign: "center",
          fontSize: "0.875rem",
          opacity: 0.7,
          maxWidth: "80%",
          wordBreak: "break-word",
        }}
      >
        {error}
      </Box>
    </Box>
  );
}

export default HlsErrorOverlay;
