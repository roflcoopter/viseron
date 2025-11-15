import { NoImage } from "@carbon/icons-react";
import Box from "@mui/material/Box";
import { useTheme } from "@mui/material/styles";
import { useState } from "react";

interface ImageWithFallbackProps {
  src: string;
  alt: string;
  style?: React.CSSProperties;
  fallbackSize?: number;
}

export function ImageWithFallback({
  src,
  alt,
  style,
  fallbackSize = 32, // Default fallback icon size
}: ImageWithFallbackProps) {
  const theme = useTheme();
  const [hasError, setHasError] = useState(false);

  const handleError = () => {
    setHasError(true);
  };

  if (hasError) {
    return (
      <Box
        style={{
          ...style,
          position: "relative",
        }}
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: theme.palette.background.default,
        }}
      >
        <NoImage
          size={fallbackSize}
          style={{
            color: theme.palette.text.secondary,
            opacity: 0.5,
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
          }}
        />
      </Box>
    );
  }

  return <img src={src} alt={alt} style={style} onError={handleError} />;
}
