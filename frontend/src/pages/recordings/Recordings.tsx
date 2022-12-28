import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import { useContext } from "react";

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
      <Grid
        container
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        spacing={2}
      >
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
