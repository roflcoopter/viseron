import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import { useContext } from "react";
import { useParams } from "react-router-dom";

import { ScrollToTopOnMount } from "components/ScrollToTop";
import { Loading } from "components/loading/Loading";
import RecordingCardDaily from "components/recording/RecordingCardDaily";
import { ViseronContext } from "context/ViseronContext";
import { useTitle } from "hooks/UseTitle";
import { objIsEmpty } from "lib/helpers";

type CameraRecordingsParams = {
  identifier: string;
};
const CameraRecordings = () => {
  const viseron = useContext(ViseronContext);
  const { identifier } = useParams<CameraRecordingsParams>();
  useTitle(
    `Recordings${
      identifier && identifier! in viseron.cameras
        ? ` | ${viseron.cameras[identifier].name}`
        : ""
    }`
  );

  if (objIsEmpty(viseron.cameras)) {
    return <Loading text="Loading Recordings" />;
  }

  if (!(identifier! in viseron.cameras)) {
    return <Loading text="Loading Recordings" />;
  }

  const camera = viseron.cameras[identifier!];

  if (objIsEmpty(camera.recordings)) {
    return (
      <Container>
        <Typography
          variant="h5"
          align="center"
        >{`No recordings for ${camera.name}`}</Typography>
      </Container>
    );
  }

  return (
    <Container>
      <ScrollToTopOnMount />
      <Typography variant="h5" align="center">
        {camera.name}
      </Typography>
      <Grid
        container
        direction="row"
        justifyContent="start"
        alignItems="center"
        spacing={2}
      >
        {Object.keys(camera.recordings)
          .sort()
          .reverse()
          .map((date) => (
            <Grid item key={date} xs={12} sm={12} md={6} lg={6} xl={4}>
              <RecordingCardDaily camera={camera} date={date} />
            </Grid>
          ))}
      </Grid>
    </Container>
  );
};

export default CameraRecordings;
