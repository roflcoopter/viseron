import { DocumentVideo, Error, SettingsEdit } from "@carbon/icons-react";
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

export function FailedCameraCard({
  failedCamera,
  compact = false,
  onClick,
}: FailedCameraCardProps) {
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
            <span>{failedCamera.name} → </span>
            <span
              style={{
                color: failedCamera.retrying
                  ? theme.palette.warning.main
                  : theme.palette.error.main,
              }}
            >
              {failedCamera.retrying ? "Retrying Setup" : "Failed Setup"}
            </span>
          </Typography>
        </CardContent>
        <CardMedia
          sx={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Error
            size={32}
            style={{
              color: failedCamera.retrying
                ? theme.palette.warning.main
                : theme.palette.error.main,
              marginTop: 5,
              marginBottom: 5,
            }}
          />
          <Typography
            align="center"
            sx={{
              fontSize: 14,
              color: failedCamera.retrying
                ? theme.palette.warning.main
                : theme.palette.error.main,
              padding: 1,
            }}
          >
            {failedCamera.error}
          </Typography>
        </CardMedia>
      </CardActionArea>
      {compact ? null : (
        <CardActions>
          <CardActionButtonLink
            title="Recordings"
            target={`/recordings/${failedCamera.identifier}`}
            startIcon={<DocumentVideo size={16} />}
          />
          <CardActionButtonLink
            title="Edit Config"
            target="/settings/configuration"
            startIcon={<SettingsEdit size={16} />}
          />
        </CardActions>
      )}
    </Card>
  );
}
