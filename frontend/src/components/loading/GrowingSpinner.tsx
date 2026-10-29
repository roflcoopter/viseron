import { Box } from "@mui/material";

interface GrowingSpinnerProps {
  color: string;
  size: number;
}

export function GrowingSpinner({ color, size }: GrowingSpinnerProps) {
  return (
    <Box
      sx={{
        width: size,
        height: size,
        borderRadius: "50%",
        bgcolor: color,
        animation: "pulse 1s ease-in-out infinite",
        "@keyframes pulse": {
          "0%": { opacity: 0.3 },
          "50%": { opacity: 1 },
          "100%": { opacity: 0.3 },
        },
      }}
    />
  );
}
