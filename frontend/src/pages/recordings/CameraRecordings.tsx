import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Grow from "@mui/material/Grow";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { ReactComponent as ServerDown } from "svg/undraw/server_down.svg";
import { ReactComponent as VoidSvg } from "svg/undraw/void.svg";

import { ScrollToTopOnMount } from "components/ScrollToTop";
import { Error } from "components/error/Error";
import { Loading } from "components/loading/Loading";
import RecordingCardDaily from "components/recording/RecordingCardDaily";
import { useTitle } from "hooks/UseTitle";
import { useCamera } from "lib/api/camera";
import { objHasValues } from "lib/helpers";
import * as types from "lib/types";

type CameraRecordingsParams = {
  camera_identifier: string;
};
const CameraRecordings = () => {
  const { camera_identifier } = useParams<
    keyof CameraRecordingsParams
  >() as CameraRecordingsParams;

  const recordingsQuery = useQuery<types.RecordingsCamera>({
    queryKey: [`/recordings/${camera_identifier}?latest&daily&failed=1`],
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
    !objHasValues<types.RecordingsCamera>(recordingsQuery.data)
  ) {
    return (
      <Error
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
      <Grid container direction="row" spacing={2}>
        {Object.keys(recordingsQuery.data)
          .sort()
          .reverse()
          .map((date) => (
            <Grow in appear key={date}>
              <Grid item key={date} xs={12} sm={12} md={6} lg={6} xl={4}>
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
