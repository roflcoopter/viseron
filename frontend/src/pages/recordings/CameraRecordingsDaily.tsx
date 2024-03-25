import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Grow from "@mui/material/Grow";
import Typography from "@mui/material/Typography";
import { useParams } from "react-router-dom";
import ServerDown from "svg/undraw/server_down.svg?react";
import VoidSvg from "svg/undraw/void.svg?react";

import { ErrorMessage } from "components/error/ErrorMessage";
import { Loading } from "components/loading/Loading";
import RecordingCard from "components/recording/RecordingCard";
import { useTitle } from "hooks/UseTitle";
import { useCamera } from "lib/api/camera";
import { useRecordings } from "lib/api/recordings";
import { objHasValues } from "lib/helpers";
import * as types from "lib/types";

type CameraRecordingsDailyParams = {
  camera_identifier: string;
  date: string;
};
const CameraRecordingsDaily = () => {
  const { camera_identifier, date } = useParams<
    keyof CameraRecordingsDailyParams
  >() as CameraRecordingsDailyParams;

  const recordingsQuery = useRecordings({
    camera_identifier,
    date,
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

  if (recordingsQuery.isLoading || cameraQuery.isLoading) {
    return <Loading text="Loading Recordings" />;
  }

  if (
    !recordingsQuery.data ||
    !objHasValues<types.RecordingsCamera>(recordingsQuery.data) ||
    !objHasValues(recordingsQuery.data[date])
  ) {
    return (
      <ErrorMessage
        text={`No recordings for ${cameraQuery.data.name} - ${date}`}
        image={
          <VoidSvg width={150} height={150} role="img" aria-label="Void" />
        }
      />
    );
  }

  return (
    <Container>
      <Typography variant="h5" align="center">
        {`${cameraQuery.data.name} - ${date}`}
      </Typography>
      <Grid container direction="row" spacing={2}>
        {Object.keys(recordingsQuery.data[date])
          .reverse()
          .map((recording) => (
            <Grow in appear key={recording}>
              <Grid item key={recording} xs={12} sm={12} md={6} lg={6} xl={4}>
                <RecordingCard
                  camera={cameraQuery.data}
                  recording={recordingsQuery.data[date][recording]}
                />
              </Grid>
            </Grow>
          ))}
      </Grid>
    </Container>
  );
};

export default CameraRecordingsDaily;
