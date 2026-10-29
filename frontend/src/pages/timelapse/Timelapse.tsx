import Button from "@mui/material/Button";
import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Grow from "@mui/material/Grow";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import ServerDown from "svg/undraw/server_down.svg?react";
import ViseronLogo from "svg/viseron-logo.svg?react";

import { ErrorMessage } from "components/error/ErrorMessage";
import { Loading } from "components/loading/Loading";
import { TimelapseCameraCard } from "components/timelapse/TimelapseCameraCard";
import { useTitle } from "hooks/UseTitle";
import { useCameras } from "lib/api/cameras";
import { useTimelapseSummary } from "lib/api/timelapse";

const TIMELAPSE_DOCS_URL =
  "https://viseron.netlify.app/docs/documentation/configuration/timelapse";

function TimelapseNotEnabled() {
  return (
    <Stack
      spacing={2}
      alignItems="center"
      justifyContent="center"
      sx={{ minHeight: "60vh", textAlign: "center", paddingX: 2 }}
    >
      <ViseronLogo width={150} height={150} role="img" aria-label="Viseron" />
      <Typography variant="h6">
        Timelapse is not enabled for any camera
      </Typography>
      <Typography color="text.secondary">
        You can configure timelapse through the storage component
      </Typography>
      <Button
        variant="contained"
        href={TIMELAPSE_DOCS_URL}
        target="_blank"
        rel="noopener"
      >
        Open Documentation
      </Button>
    </Stack>
  );
}

function Timelapse() {
  useTitle("Timelapse");

  const cameras = useCameras({});
  const summary = useTimelapseSummary();

  if (cameras.isPending || summary.isPending) {
    return <Loading text="Loading Timelapse" />;
  }

  if (cameras.isError || summary.isError) {
    return (
      <ErrorMessage
        text="Error loading recordings"
        subtext={cameras.error?.message || summary.error?.message}
        image={
          <ServerDown width={150} height={150} role="img" aria-label="Void" />
        }
      />
    );
  }

  const timelapseCameras = Object.values(cameras.data ?? {})
    .filter((camera) => camera.timelapse)
    .sort((a, b) => a.identifier.localeCompare(b.identifier));

  if (timelapseCameras.length === 0) {
    return <TimelapseNotEnabled />;
  }

  return (
    <Container sx={{ paddingX: { xs: 1, md: 2 }, paddingY: 0.5 }}>
      <Grid container direction="row" spacing={1}>
        {timelapseCameras.map((camera) => (
          <Grow in appear key={camera.identifier}>
            <Grid size={{ xs: 12, sm: 12, md: 6, lg: 4, xl: 3 }}>
              <TimelapseCameraCard
                camera={camera}
                summary={summary.data?.cameras[camera.identifier]}
              />
            </Grid>
          </Grow>
        ))}
      </Grid>
    </Container>
  );
}

export default Timelapse;
