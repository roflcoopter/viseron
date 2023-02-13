import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";
import { useContext } from "react";
import { useParams } from "react-router-dom";

import { Loading } from "components/loading/Loading";
import RecordingCard from "components/recording/RecordingCard";
import { ViseronContext } from "context/ViseronContext";
import { useTitle } from "hooks/UseTitle";
import { objHasValues } from "lib/helpers";
import * as types from "lib/types";

type CameraRecordingsDailyParams = {
  identifier: string;
  date: string;
};
const CameraRecordingsDaily = () => {
  const viseron = useContext(ViseronContext);
  const { identifier, date } = useParams<
    keyof CameraRecordingsDailyParams
  >() as CameraRecordingsDailyParams;
  useTitle(
    `Recordings${
      identifier && identifier in viseron.cameras
        ? ` | ${viseron.cameras[identifier].name}`
        : ""
    }`
  );

  const { status, data: recordings } = useQuery<types.RecordingsCamera>({
    queryKey: [`/recordings/${identifier}/${date}`],
  });

  if (status === "error") {
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
    status === "loading" ||
    !objHasValues<typeof viseron.cameras>(viseron.cameras) ||
    !(identifier in viseron.cameras)
  ) {
    return <Loading text="Loading Recordings" />;
  }

  const camera = viseron.cameras[identifier];

  if (
    !recordings ||
    !objHasValues<types.RecordingsCamera>(recordings) ||
    !objHasValues(recordings[date])
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
      <Typography variant="h5" align="center">
        {`${camera.name} - ${date}`}
      </Typography>
      <Grid container direction="row" spacing={2}>
        {Object.keys(recordings[date])
          .sort()
          .reverse()
          .map((recording) => (
            <Grid item key={recording} xs={12} sm={12} md={6} lg={6} xl={4}>
              <RecordingCard
                camera={camera}
                recording={recordings[date][recording]}
              />
            </Grid>
          ))}
      </Grid>
    </Container>
  );
};

export default CameraRecordingsDaily;
