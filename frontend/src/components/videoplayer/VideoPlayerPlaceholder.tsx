import Image from "@roflcoopter/material-ui-image";
import { useTheme } from "@mui/material/styles";

import * as types from "lib/types";

interface VideoPlayerPlaceholderProps {
  camera: types.Camera | types.FailedCamera;
}

const blankImage =
  "data:image/svg+xml;charset=utf8,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%3E%3C/svg%3E";

export default function VideoPlayerPlaceholder({
  camera,
}: VideoPlayerPlaceholderProps) {
  const theme = useTheme();
  return (
    <Image
      src={blankImage}
      aspectRatio={camera.width / camera.height}
      color={theme.palette.background.default}
      errorIcon={Image.defaultProps!.loading}
    />
  );
}
