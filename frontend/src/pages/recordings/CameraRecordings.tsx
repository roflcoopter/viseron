import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid2";
import Grow from "@mui/material/Grow";
import Typography from "@mui/material/Typography";
import { useParams } from "react-router-dom";
import ServerDown from "svg/undraw/server_down.svg?react";
import VoidSvg from "svg/undraw/void.svg?react";

import { ScrollToTopOnMount } from "components/ScrollToTop";
import { ErrorMessage } from "components/error/ErrorMessage";
import { Loading } from "components/loading/Loading";
import RecordingCardDaily from "components/recording/RecordingCardDaily";
import { useTitle } from "hooks/UseTitle";
import { useCamera } from "lib/api/camera";
import { useRecordings } from "lib/api/recordings";
import { objHasValues } from "lib/helpers";
import * as types from "lib/types";

type CameraRecordingsParams = {
  camera_identifier: string;
};
const CameraRecordings = () => {
  const { camera_identifier } = useParams<
    keyof CameraRecordingsParams
  >() as CameraRecordingsParams;

  const recordingsQuery = useRecordings({
    camera_identifier,
    latest: true,
    daily: true,
    failed: true,
  });
  const cameraQuery = useCamera(camera_identifier, true);

  useTitle(
    `Recordings${cameraQuery.data ? ` | ${cameraQuery.data.name}` : ""}`,
  );

  if (recordingsQuery.isError || cameraQuery.isError) {
    return (
      <ErrorMessage
        text={`Error loading recordings`}
        subtext={recordingsQuery.error?.message || cameraQuery.error?.message}
        image={
          <ServerDown width={150} height={150} role="img" aria-label="Void" />
        }
      />
    );
  }

  if (recordingsQuery.isPending || cameraQuery.isPending) {
    return <Loading text="Loading Recordings" />;
  }

  if (
    !recordingsQuery.data ||
    !objHasValues<types.RecordingsCamera>(recordingsQuery.data)
  ) {
    return (
      <ErrorMessage
        text={`No recordings for ${cameraQuery.data.name}`}
        image={
          <VoidSvg width={150} height={150} role="img" aria-label="Void" />
        }
      />
    );
  }

  return (
    <Container>
      <ScrollToTopOnMount />
      <Typography variant="h5" align="center">
        {cameraQuery.data.name}
      </Typography>
      <Grid container direction="row" spacing={1}>
        {Object.keys(recordingsQuery.data)
          .sort()
          .reverse()
          .map((date) => (
            <Grow in appear key={date}>
              <Grid
                key={date}
                size={{
                  xs: 12,
                  sm: 12,
                  md: 6,
                  lg: 6,
                  xl: 4,
                }}
              >
                <RecordingCardDaily
                  camera={cameraQuery.data}
                  recording={Object.values(recordingsQuery.data[date])[0]}
                  date={date}
                />
              </Grid>
            </Grow>
          ))}
      </Grid>
    </Container>
  );
};

export default CameraRecordings;
