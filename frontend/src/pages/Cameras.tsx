import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import { useContext } from "react";

import CameraCard from "components/CameraCard";
import { Loading } from "components/loading/Loading";
import { ViseronContext } from "context/ViseronContext";
import { useTitle } from "hooks/UseTitle";
import { objIsEmpty } from "lib/helpers";

const Cameras = () => {
  useTitle("Cameras");
  const viseron = useContext(ViseronContext);

  if (objIsEmpty(viseron.cameras)) {
    return <Loading text="Loading Cameras" />;
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
            xl={6}
            key={viseron.cameras[camera].identifier}
          >
            <CameraCard camera={viseron.cameras[camera]} />
          </Grid>
        ))}
      </Grid>
    </Container>
  );
};

export default Cameras;
