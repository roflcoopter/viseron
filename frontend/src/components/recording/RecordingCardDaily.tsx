import {
  CloudOffline,
  FolderDetailsReference,
  TrashCan,
} from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardActions from "@mui/material/CardActions";
import CardContent from "@mui/material/CardContent";
import CardMedia from "@mui/material/CardMedia";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import LazyLoad from "react-lazyload";
import { Link } from "react-router-dom";

import MutationIconButton from "components/buttons/MutationIconButton";
import VideoPlayerPlaceholder from "components/player/videoplayer/VideoPlayerPlaceholder";
import { useAuthContext } from "context/AuthContext";
import { useDeleteRecording } from "lib/api/recordings";
import { getTimeFromDate, getVideoElement, objHasValues } from "lib/helpers";
import * as types from "lib/types";

interface RecordingCardDailyProps {
  camera: types.Camera | types.FailedCamera;
  date: string;
  recording: types.Recording | null;
}

export default function RecordingCardDaily({
  camera,
  date,
  recording,
}: RecordingCardDailyProps) {
  const theme = useTheme();
  const { auth, user } = useAuthContext();
  const deleteRecording = useDeleteRecording();

  return (
    <Card
      variant="outlined"
      sx={
        camera.failed
          ? {
              border: `2px solid ${
                camera.retrying
                  ? theme.palette.warning.main
                  : theme.palette.error.main
              }`,
            }
          : undefined
      }
    >
      <CardContent>
        <Typography variant="h6">{date}</Typography>
      </CardContent>
      <CardMedia>
        <LazyLoad
          height={200}
          offset={500}
          placeholder={
            <VideoPlayerPlaceholder
              aspectRatio={camera.mainstream.width / camera.mainstream.height}
            />
          }
        >
          {objHasValues<types.Recording>(recording) ? (
            getVideoElement(camera, recording, auth.enabled)
          ) : (
            <Box
              sx={{
                width: "100%",
                height: 200,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                backgroundColor: theme.palette.background.default,
              }}
            >
              <CloudOffline
                size={48}
                style={{
                  color: theme.palette.text.secondary,
                  opacity: 0.5,
                }}
              />
            </Box>
          )}
        </LazyLoad>
      </CardMedia>
      <CardActions>
        <Stack
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          spacing={2}
          sx={{ width: "100%", paddingX: 1 }}
        >
          {objHasValues<types.Recording>(recording) ? (
            <Typography variant="body2" sx={{ whiteSpace: "pre-line" }}>
              Latest recording:{"\n"}
              <span style={{ color: theme.palette.info.main }}>
                {getTimeFromDate(new Date(recording.start_time))}
              </span>
            </Typography>
          ) : (
            <Typography variant="body2">No recordings found</Typography>
          )}
          <Stack direction="row" spacing={1}>
            <Tooltip title="View All Videos">
              <span>
                <IconButton
                  component={Link}
                  to={`/recordings/${camera.identifier}/${date}`}
                  disabled={!objHasValues(recording)}
                >
                  <FolderDetailsReference size={20} />
                </IconButton>
              </span>
            </Tooltip>
            {!user || user.role === "admin" || user.role === "write" ? (
              <Tooltip title="Delete All Videos">
                <span>
                  <MutationIconButton
                    mutation={deleteRecording}
                    color="error"
                    onClick={() => {
                      deleteRecording.mutate({
                        identifier: camera.identifier,
                        date,
                        failed: camera.failed,
                      });
                    }}
                  >
                    <TrashCan size={20} />
                  </MutationIconButton>
                </span>
              </Tooltip>
            ) : null}
          </Stack>
        </Stack>
      </CardActions>
    </Card>
  );
}
