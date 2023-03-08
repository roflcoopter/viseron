import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import { useContext } from "react";

import CameraCard from "components/CameraCard";
import { Loading } from "components/loading/Loading";
import { ViseronContext } from "context/ViseronContext";
import { useTitle } from "hooks/UseTitle";
import { objHasValues } from "lib/helpers";

const Cameras = () => {
  useTitle("Cameras");
  const { cameras } = useContext(ViseronContext);

  if (!objHasValues<typeof cameras>(cameras)) {
    return <Loading text="Loading Cameras" />;
  }

  return (
    <Container>
      <Typography variant="h5" align="center">
        Cameras
      </Typography>
      <Grid container direction="row" spacing={2}>
        {cameras.map((camera_identifier) => (
          <Grid
            item
            xs={12}
            sm={12}
            md={6}
            lg={6}
            xl={4}
            key={camera_identifier}
          >
            <CameraCard camera_identifier={camera_identifier} />
          </Grid>
        ))}
      </Grid>
    </Container>
  );
};

export default Cameras;
