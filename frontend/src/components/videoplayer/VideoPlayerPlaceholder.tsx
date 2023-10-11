import Image from "@jy95/material-ui-image";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";

interface VideoPlayerPlaceholderProps {
  aspectRatio?: number;
  text?: string;
}

const blankImage =
  "data:image/svg+xml;charset=utf8,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%3E%3C/svg%3E";

export default function VideoPlayerPlaceholder({
  aspectRatio = 1920 / 1080,
  text,
}: VideoPlayerPlaceholderProps) {
  const theme = useTheme();

  return (
    <Box sx={{ position: "relative" }}>
      <Image
        src={blankImage}
        aspectRatio={aspectRatio}
        color={theme.palette.background.default}
        errorIcon={Image.defaultProps!.loading}
      />
      {text ? (
        <Typography
          variant="uppercase"
          style={{
            fontSize: "1.5vw",
            textAlign: "center",
            position: "absolute",
            opacity: "0.5",
            top: "0",
            bottom: "0",
            left: "0",
            right: "0",
            height: "fit-content",
            margin: "auto",
          }}
        >
          {text}
        </Typography>
      ) : null}
    </Box>
  );
}
