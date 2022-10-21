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

type RecordingsParams = {
  identifier: string;
};
const Recordings = () => {
  const viseron = useContext(ViseronContext);
  const { identifier } = useParams<RecordingsParams>();
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
      <Grid container direction="row" spacing={2}>
        {Object.keys(camera.recordings)
          .sort()
          .reverse()
          .map((date) => (
            <Grid item key={date} xs={12}>
              <Typography variant="h5">{date}</Typography>
              <Grid
                container
                direction="row"
                justifyContent="start"
                spacing={2}
              >
                {Object.keys(camera.recordings[date])
                  .sort()
                  .reverse()
                  .map((recording) => (
                    <Grid
                      item
                      key={recording}
                      xs={12}
                      sm={6}
                      md={6}
                      lg={6}
                      xl={6}
                    >
                      <RecordingCard
                        recording={camera.recordings[date][recording]}
                      />
                    </Grid>
                  ))}
              </Grid>
            </Grid>
          ))}
      </Grid>
    </Container>
  );
};

export default Recordings;
