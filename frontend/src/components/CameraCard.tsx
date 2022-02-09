import Image from "@jy95/material-ui-image";
import { CardActionArea, CardActions } from "@mui/material";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";

import {
  CardActionButtonHref,
  CardActionButtonLink,
} from "components/CardActionButton";
import * as types from "lib/types";

interface CameraCardProps {
  camera: types.Camera;
}

export default function CameraCard({ camera }: CameraCardProps) {
  const theme = useTheme();

  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="h5" align="center">
          {camera.name}
        </Typography>
      </CardContent>
      <CardActionArea>
        <Image
          src={`/${camera.identifier}/mjpeg-stream`}
          alt={camera.name}
          animationDuration={1000}
          aspectRatio={camera.width / camera.height}
          color={theme.palette.background.default}
        />
      </CardActionArea>
      <CardActions>
        <CardActionButtonLink
          title="Recordings"
          target={`/recordings/${camera.identifier}`}
        />
        <CardActionButtonHref
          title="Live View"
          target={`/${camera.identifier}/mjpeg-stream`}
        />
      </CardActions>
    </Card>
  );
}
