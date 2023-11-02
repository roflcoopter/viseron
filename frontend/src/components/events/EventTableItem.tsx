import Image from "@jy95/material-ui-image";
import Card from "@mui/material/Card";
import CardActionArea from "@mui/material/CardActionArea";
import CardMedia from "@mui/material/CardMedia";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import LazyLoad from "react-lazyload";

import VideoPlayerPlaceholder from "components/videoplayer/VideoPlayerPlaceholder";
import { getTimeFromDate } from "lib/helpers";
import * as types from "lib/types";

type EventTableItemProps = {
  camera: types.Camera;
  recording: types.Recording;
  setSelectedRecording: (recording: types.Recording) => void;
  selected: boolean;
};
export const EventTableItem = ({
  camera,
  recording,
  setSelectedRecording,
  selected,
}: EventTableItemProps) => {
  const theme = useTheme();
  return (
    <Card
      variant="outlined"
      square
      sx={{
        border: selected
          ? `2px solid ${theme.palette.primary[400]}`
          : "2px solid transparent",
        borderRadius: "5px",
        boxShadow: "none",
      }}
    >
      <CardActionArea onClick={() => setSelectedRecording(recording)}>
        <Grid
          container
          direction="row"
          justifyContent="flex-end"
          alignItems="center"
        >
          <Grid item xs={6}>
            <Typography variant="body2" align="center">
              {getTimeFromDate(new Date(recording.start_time))}
            </Typography>
          </Grid>
          <Grid item xs={6}>
            <CardMedia
              sx={{
                borderRadius: "5px",
                overflow: "hidden",
              }}
            >
              <LazyLoad
                overflow
                placeholder={
                  <VideoPlayerPlaceholder
                    aspectRatio={camera.width / camera.height}
                  />
                }
              >
                <Image
                  src={recording.thumbnail_path}
                  aspectRatio={camera.width / camera.height}
                  color={theme.palette.background.default}
                  animationDuration={1000}
                />
              </LazyLoad>
            </CardMedia>
          </Grid>
        </Grid>
      </CardActionArea>
    </Card>
  );
};
