import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import { useContext } from "react";
import { useParams } from "react-router-dom";

import { ScrollToTopOnMount } from "components/ScrollToTop";
import { Loading } from "components/loading/Loading";
import RecordingCard from "components/recording/RecordingCard";
import { ViseronContext } from "context/ViseronContext";
import { useTitle } from "hooks/UseTitle";
import { objIsEmpty } from "lib/helpers";

type CameraRecordingsDailyParams = {
  identifier: string;
  date: string;
};
const CameraRecordingsDaily = () => {
  const viseron = useContext(ViseronContext);
  const { identifier, date } = useParams<CameraRecordingsDailyParams>();
  useTitle(
    `Recordings${
      identifier && identifier! in viseron.cameras
        ? ` | ${viseron.cameras[identifier].name}`
        : ""
    }`
  );

  if (
    objIsEmpty(viseron.cameras) ||
    !(identifier! in viseron.cameras) ||
    !date
  ) {
    return <Loading text="Loading Recordings" />;
  }

  const camera = viseron.cameras[identifier!];

  if (
    objIsEmpty(camera.recordings) ||
    !camera.recordings[date] ||
    objIsEmpty(camera.recordings[date])
  ) {
    return (
      <Container>
        <Typography
          variant="h5"
          align="center"
        >{`No recordings for ${camera.name} - ${date}`}</Typography>
      </Container>
    );
  }

  return (
    <Container>
      <ScrollToTopOnMount />
      <Typography variant="h5" align="center">
        {`${camera.name} - ${date}`}
      </Typography>
      <Grid container direction="row" spacing={2}>
        {Object.keys(camera.recordings[date])
          .sort()
          .reverse()
          .map((recording) => (
            <Grid item key={recording} xs={12} sm={12} md={6} lg={6} xl={4}>
              <RecordingCard
                camera={camera}
                recording={camera.recordings[date][recording]}
              />
            </Grid>
          ))}
      </Grid>
    </Container>
  );
};

export default CameraRecordingsDaily;
