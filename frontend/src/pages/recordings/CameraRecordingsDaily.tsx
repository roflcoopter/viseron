import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Grow from "@mui/material/Grow";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { ReactComponent as ServerDown } from "svg/undraw/server_down.svg";
import { ReactComponent as VoidSvg } from "svg/undraw/void.svg";

import { Error } from "components/error/Error";
import { Loading } from "components/loading/Loading";
import RecordingCard from "components/recording/RecordingCard";
import { useTitle } from "hooks/UseTitle";
import { useCamera } from "lib/api/camera";
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
  const recordingsQuery = useQuery<types.RecordingsCamera>({
    queryKey: [`/recordings/${camera_identifier}/${date}?failed=1`],
  });
  const cameraQuery = useCamera(camera_identifier, true);

  useTitle(
    `Recordings${cameraQuery.data ? ` | ${cameraQuery.data.name}` : ""}`
  );

  if (recordingsQuery.isError || cameraQuery.isError) {
    return (
      <Error
        text={`Error loading recordings`}
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
      <Error
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
