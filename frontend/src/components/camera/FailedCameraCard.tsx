import Card from "@mui/material/Card";
import CardActions from "@mui/material/CardActions";
import CardContent from "@mui/material/CardContent";
import CardMedia from "@mui/material/CardMedia";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";

import { CardActionButtonLink } from "components/CardActionButton";
import * as types from "lib/types";

interface FailedCameraCardProps {
  failedCamera: types.FailedCamera;
}

export default function FailedCameraCard({
  failedCamera,
}: FailedCameraCardProps) {
  const theme = useTheme();

  return (
    <Card
      variant="outlined"
      sx={{
        // Vertically space items evenly to accommodate different aspect ratios
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        border: `2px solid ${
          failedCamera.retrying
            ? theme.palette.warning.main
            : theme.palette.error.main
        }`,
      }}
    >
      <CardContent>
        <Typography variant="h5" align="center">
          {failedCamera.name} -{" "}
          {failedCamera.retrying ? "Retrying setup" : "Failed setup"}
        </Typography>
      </CardContent>
      <CardMedia>
        <Typography align="center">{failedCamera.error}</Typography>
      </CardMedia>
      <CardActions>
        <CardActionButtonLink
          title="Recordings"
          target={`/recordings/${failedCamera.identifier}`}
        />
        <CardActionButtonLink title="Edit Config" target={`/configuration`} />
      </CardActions>
    </Card>
  );
}
