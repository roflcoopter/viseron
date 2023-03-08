import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import { useContext } from "react";

import { ScrollToTopOnMount } from "components/ScrollToTop";
import { Loading } from "components/loading/Loading";
import RecordingCardLatest from "components/recording/RecordingCardLatest";
import { ViseronContext } from "context/ViseronContext";
import { useTitle } from "hooks/UseTitle";
import { objHasValues } from "lib/helpers";

const Recordings = () => {
  const { cameras } = useContext(ViseronContext);
  useTitle("Recordings");

  if (!objHasValues<typeof cameras>(cameras)) {
    return <Loading text="Loading Recordings" />;
  }

  return (
    <Container>
      <ScrollToTopOnMount />
      <Typography variant="h5" align="center">
        Recordings
      </Typography>
      <Grid container direction="row" spacing={2}>
        {Object.values(cameras).map((camera_identifier) => (
          <Grid
            item
            xs={12}
            sm={12}
            md={6}
            lg={6}
            xl={4}
            key={camera_identifier}
          >
            <RecordingCardLatest camera_identifier={camera_identifier} />
          </Grid>
        ))}
      </Grid>
    </Container>
  );
};

export default Recordings;
