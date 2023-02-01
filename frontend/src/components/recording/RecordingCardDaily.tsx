import DeleteForeverIcon from "@mui/icons-material/DeleteForever";
import VideoFileIcon from "@mui/icons-material/VideoFile";
import { CardActions, CardMedia } from "@mui/material";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import LazyLoad from "react-lazyload";
import { Link } from "react-router-dom";

import MutationIconButton from "components/buttons/MutationIconButton";
import VideoPlayerPlaceholder from "components/videoplayer/VideoPlayerPlaceholder";
import { deleteRecordingParams, useDeleteRecording } from "lib/api/client";
import { getVideoElement, objHasValues } from "lib/helpers";
import * as types from "lib/types";

interface RecordingCardDailyProps {
  camera: types.Camera;
  date: string;
  recording: types.Recording | null;
}

export default function RecordingCardDaily({
  camera,
  date,
  recording,
}: RecordingCardDailyProps) {
  const deleteRecording = useDeleteRecording();

  return (
    <LazyLoad height={200}>
      <Card variant="outlined">
        <CardContent>
          <Typography variant="h5" align="center">
            {date}
          </Typography>
          {objHasValues<types.Recording>(recording) ? (
            <Typography align="center">{`Last recording: ${
              recording.filename.split(".")[0]
            }`}</Typography>
          ) : (
            <Typography align="center">No recordings found</Typography>
          )}
        </CardContent>
        <CardMedia>
          <LazyLoad
            height={200}
            offset={500}
            placeholder={<VideoPlayerPlaceholder camera={camera} />}
          >
            {getVideoElement(camera, recording)}
          </LazyLoad>
        </CardMedia>
        <CardActions>
          <Stack direction="row" spacing={1} sx={{ ml: "auto" }}>
            <Tooltip title="View Recordings">
              <span>
                <IconButton
                  component={Link}
                  to={`/recordings/${camera.identifier}/${date}`}
                  disabled={!objHasValues(recording)}
                >
                  <VideoFileIcon />
                </IconButton>
              </span>
            </Tooltip>
            <Tooltip title="Delete Recordings">
              <MutationIconButton<deleteRecordingParams>
                mutation={deleteRecording}
                onClick={() => {
                  deleteRecording.mutate({
                    identifier: camera.identifier,
                    date,
                  });
                }}
              >
                <DeleteForeverIcon />
              </MutationIconButton>
            </Tooltip>
          </Stack>
        </CardActions>
      </Card>
    </LazyLoad>
  );
}
