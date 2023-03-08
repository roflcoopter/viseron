import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";
import { useContext } from "react";
import { useParams } from "react-router-dom";

import { ScrollToTopOnMount } from "components/ScrollToTop";
import { Loading } from "components/loading/Loading";
import RecordingCardDaily from "components/recording/RecordingCardDaily";
import { ViseronContext } from "context/ViseronContext";
import { useTitle } from "hooks/UseTitle";
import { useCamera } from "lib/api/camera";
import { objHasValues } from "lib/helpers";
import * as types from "lib/types";

type CameraRecordingsParams = {
  camera_identifier: string;
};
const CameraRecordings = () => {
  const { cameras } = useContext(ViseronContext);
  const { camera_identifier } = useParams<
    keyof CameraRecordingsParams
  >() as CameraRecordingsParams;
  const recordingsQuery = useQuery<types.RecordingsCamera>({
    queryKey: [`/recordings/${camera_identifier}?latest&daily`],
  });
  const cameraQuery = useCamera({ camera_identifier });
  useTitle(
    `Recordings${
      cameras.includes(camera_identifier) && cameraQuery.data
        ? ` | ${cameraQuery.data.name}`
        : ""
    }`
  );

  if (recordingsQuery.isError || cameraQuery.isError) {
    return (
      <Container>
        <Typography
          variant="h5"
          align="center"
        >{`Error loading recordings`}</Typography>
      </Container>
    );
  }

  if (
    recordingsQuery.isLoading ||
    cameraQuery.isLoading ||
    !objHasValues<typeof cameras>(cameras) ||
    !cameras.includes(camera_identifier)
  ) {
    return <Loading text="Loading Recordings" />;
  }

  if (
    !recordingsQuery.data ||
    !objHasValues<types.RecordingsCamera>(recordingsQuery.data)
  ) {
    return (
      <Container>
        <Typography
          variant="h5"
          align="center"
        >{`No recordings for ${cameraQuery.data.name}`}</Typography>
      </Container>
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
            <Grid item key={date} xs={12} sm={12} md={6} lg={6} xl={4}>
              <RecordingCardDaily
                camera={cameraQuery.data}
                recording={Object.values(recordingsQuery.data[date])[0]}
                date={date}
              />
            </Grid>
          ))}
      </Grid>
    </Container>
  );
};

export default CameraRecordings;
