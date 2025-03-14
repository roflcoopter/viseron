import Card from "@mui/material/Card";
import CardActionArea from "@mui/material/CardActionArea";
import CardActions from "@mui/material/CardActions";
import CardContent from "@mui/material/CardContent";
import CardMedia from "@mui/material/CardMedia";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";

import { CardActionButtonLink } from "components/CardActionButton";
import * as types from "lib/types";

interface FailedCameraCardProps {
  failedCamera: types.FailedCamera;
  compact?: boolean;
  onClick?: (
    event: React.MouseEvent<HTMLButtonElement, MouseEvent>,
    camera: types.FailedCamera,
  ) => void;
}

export const FailedCameraCard = ({
  failedCamera,
  compact = false,
  onClick,
}: FailedCameraCardProps) => {
  const theme = useTheme();

  return (
    <Card
      variant="outlined"
      sx={[
        {
          // Vertically space items evenly to accommodate different aspect ratios
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          height: "100%",
          border: `2px solid ${
            failedCamera.retrying
              ? theme.palette.warning.main
              : theme.palette.error.main
          }`,
        },
        compact ? { position: "relative" } : null,
      ]}
    >
      <CardActionArea
        onClick={onClick ? (event) => onClick(event, failedCamera) : undefined}
        sx={onClick ? null : { pointerEvents: "none" }}
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
      </CardActionArea>
      {compact ? null : (
        <CardActions>
          <CardActionButtonLink
            title="Recordings"
            target={`/recordings/${failedCamera.identifier}`}
          />
          <CardActionButtonLink title="Edit Config" target={`/configuration`} />
        </CardActions>
      )}
    </Card>
  );
};
