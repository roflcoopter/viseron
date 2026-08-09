import {
  CenterSquare,
  Download,
  FaceActivated,
  Movement,
  TrashCan,
} from "@carbon/icons-react";
import Card from "@mui/material/Card";
import CardActions from "@mui/material/CardActions";
import CardContent from "@mui/material/CardContent";
import CardMedia from "@mui/material/CardMedia";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import { useState } from "react";
import LazyLoad from "react-lazyload";

import MutationIconButton from "components/buttons/MutationIconButton";
import ConfirmDeleteDialog from "components/dialog/ConfirmDeleteDialog";
import LicensePlateRecognitionIcon from "components/icons/LicensePlateRecognition";
import { getVideoElement } from "components/player/utils";
import VideoPlayerPlaceholder from "components/player/videoplayer/VideoPlayerPlaceholder";
import { useAuthContext } from "context/AuthContext";
import { useExportRecording } from "hooks/UseExportRecording";
import { useDeleteRecording } from "lib/api/recordings";
import {
  getDayjsFromDateTimeString,
  getTimeStringFromDayjs,
} from "lib/helpers/dates";
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
  const { user } = useAuthContext();
  const deleteRecording = useDeleteRecording();
  const exportRecording = useExportRecording();
  const [confirmOpen, setConfirmOpen] = useState(false);

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
            {getTimeStringFromDayjs(
              getDayjsFromDateTimeString(recording.start_time),
            )}
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
          {getVideoElement(camera, recording)}
        </LazyLoad>
      </CardMedia>
      <CardActions>
        <Stack direction="row" spacing={1} sx={{ ml: "auto" }}>
          <Tooltip title="Download Recording">
            <IconButton
              onClick={() => {
                exportRecording(camera.identifier, recording.id);
              }}
            >
              <Download size={20} />
            </IconButton>
          </Tooltip>
          {!user || user.role === "admin" || user.role === "write" ? (
            <Tooltip title="Delete Recording">
              <MutationIconButton
                mutation={deleteRecording}
                color="error"
                onClick={() => setConfirmOpen(true)}
              >
                <TrashCan size={20} />
              </MutationIconButton>
            </Tooltip>
          ) : null}
        </Stack>
        {!user || user.role === "admin" || user.role === "write" ? (
          <ConfirmDeleteDialog
            open={confirmOpen}
            onClose={() => setConfirmOpen(false)}
            onConfirm={() => {
              deleteRecording.mutate(
                {
                  identifier: camera.identifier,
                  recording_id: recording.id,
                  failed: camera.failed,
                },
                { onSuccess: () => setConfirmOpen(false) },
              );
            }}
            isPending={deleteRecording.isPending}
            title="Delete recording"
            description="Delete this recording? This action cannot be undone."
          />
        ) : null}
      </CardActions>
    </Card>
  );
}
