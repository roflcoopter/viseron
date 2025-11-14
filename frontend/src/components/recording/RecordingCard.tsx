import {
  CenterSquare,
  FaceActivated,
  Movement,
  TrashCan,
} from "@carbon/icons-react";
import Card from "@mui/material/Card";
import CardActions from "@mui/material/CardActions";
import CardContent from "@mui/material/CardContent";
import CardMedia from "@mui/material/CardMedia";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import LazyLoad from "react-lazyload";

import MutationIconButton from "components/buttons/MutationIconButton";
import LicensePlateRecognitionIcon from "components/icons/LicensePlateRecognition";
import VideoPlayerPlaceholder from "components/player/videoplayer/VideoPlayerPlaceholder";
import { useAuthContext } from "context/AuthContext";
import { useDeleteRecording } from "lib/api/recordings";
import { getTimeFromDate, getVideoElement } from "lib/helpers";
import * as types from "lib/types";

interface RecordingCardInterface {
  camera: types.Camera | types.FailedCamera;
  recording: types.Recording;
}

export default function RecordingCard({
  camera,
  recording,
}: RecordingCardInterface) {
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
        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
          justifyContent="space-between"
        >
          {recording.trigger_type === "motion" ? (
            <Tooltip title="Motion Detection">
              <Movement size={20} />
            </Tooltip>
          ) : recording.trigger_type === "object" ? (
            <Tooltip title="Object Detection">
              <CenterSquare size={20} />
            </Tooltip>
          ) : recording.trigger_type === "face_recognition" ? (
            <Tooltip title="Face Recognition">
              <FaceActivated size={20} />
            </Tooltip>
          ) : recording.trigger_type === "license_plate_recognition" ? (
            <Tooltip title="License Plate Recognition">
              <LicensePlateRecognitionIcon />
            </Tooltip>
          ) : null}
          <Typography>
            {getTimeFromDate(new Date(recording.start_time))}
          </Typography>
        </Stack>
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
          {getVideoElement(camera, recording, auth.enabled)}
        </LazyLoad>
      </CardMedia>
      {!user || user.role === "admin" || user.role === "write" ? (
        <CardActions>
          <Stack direction="row" spacing={1} sx={{ ml: "auto" }}>
            <Tooltip title="Delete Recording">
              <MutationIconButton
                mutation={deleteRecording}
                color="error"
                onClick={() => {
                  deleteRecording.mutate({
                    identifier: camera.identifier,
                    recording_id: recording.id,
                    failed: camera.failed,
                  });
                }}
              >
                <TrashCan size={20} />
              </MutationIconButton>
            </Tooltip>
          </Stack>
        </CardActions>
      ) : null}
    </Card>
  );
}
