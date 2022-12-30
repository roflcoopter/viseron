import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import { useContext } from "react";

import { ScrollToTopOnMount } from "components/ScrollToTop";
import { Loading } from "components/loading/Loading";
import RecordingCardLatest from "components/recording/RecordingCardLatest";
import { ViseronContext } from "context/ViseronContext";
import { useTitle } from "hooks/UseTitle";
import { objIsEmpty } from "lib/helpers";

const Recordings = () => {
  const viseron = useContext(ViseronContext);
  useTitle("Recordings");

  if (objIsEmpty(viseron.cameras)) {
    return <Loading text="Loading Recordings" />;
  }

  return (
    <Container>
      <ScrollToTopOnMount />
      <Typography variant="h5" align="center">
        Recordings
      </Typography>
      <Grid container direction="row" spacing={2}>
        {Object.keys(viseron.cameras).map((camera) => (
          <Grid
            item
            xs={12}
            sm={12}
            md={6}
            lg={6}
            xl={4}
            key={viseron.cameras[camera].identifier}
          >
            <RecordingCardLatest camera={viseron.cameras[camera]} />
          </Grid>
        ))}
      </Grid>
    </Container>
  );
};

export default Recordings;
