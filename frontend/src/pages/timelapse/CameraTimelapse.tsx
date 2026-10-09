import { VideoAdd } from "@carbon/icons-react";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Container from "@mui/material/Container";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import ServerDown from "svg/undraw/server_down.svg?react";
import VoidSvg from "svg/undraw/void.svg?react";

import { ErrorMessage } from "components/error/ErrorMessage";
import { Loading } from "components/loading/Loading";
import { TimelapsePlayer } from "components/timelapse/TimelapsePlayer";
import { TimelapseRangeSelector } from "components/timelapse/TimelapseRangeSelector";
import { TimelapseRenderDialog } from "components/timelapse/TimelapseRenderDialog";
import {
  TimelapseSelection,
  parseDensity,
  parseSelection,
  resolveRange,
  selectionParams,
} from "components/timelapse/utils";
import { isRenderActive, useRenderTimelapse } from "hooks/UseRenderTimelapse";
import { useTitle } from "hooks/UseTitle";
import { useCamera } from "lib/api/camera";
import { useTimelapseFrames } from "lib/api/timelapse";
import { getDayjs } from "lib/helpers/dates";

type CameraTimelapseParams = {
  camera_identifier: string;
};

function CameraTimelapse() {
  const { camera_identifier } = useParams<
    keyof CameraTimelapseParams
  >() as CameraTimelapseParams;
  const [searchParams, setSearchParams] = useSearchParams();
  const selection = parseSelection(searchParams);
  const density = parseDensity(searchParams);
  // Presets are relative to when they were selected, not to every render
  const [now, setNow] = useState(getDayjs);
  const range = resolveRange(selection, now);
  const [renderOpen, setRenderOpen] = useState(false);
  const render = useRenderTimelapse();

  const cameraQuery = useCamera(camera_identifier);
  const framesQuery = useTimelapseFrames({
    camera_identifier,
    start: range.start,
    end: range.end,
    max_frames: density,
    configOptions: { enabled: !!cameraQuery.data?.timelapse },
  });

  useTitle(`Timelapse${cameraQuery.data ? ` | ${cameraQuery.data.name}` : ""}`);

  const setSelection = (next: TimelapseSelection) => {
    setNow(getDayjs());
    setSearchParams(selectionParams(next, density));
  };

  const setDensity = (next: number) => {
    setSearchParams(selectionParams(selection, next));
  };

  if (cameraQuery.isError) {
    return (
      <ErrorMessage
        text="Error loading camera"
        subtext={cameraQuery.error.message}
        image={
          <ServerDown width={150} height={150} role="img" aria-label="Error" />
        }
      />
    );
  }

  if (cameraQuery.isPending) {
    return <Loading text="Loading Timelapse" />;
  }

  if (!cameraQuery.data.timelapse) {
    return (
      <ErrorMessage
        text={`Timelapse is not enabled for ${cameraQuery.data.name}`}
        image={
          <VoidSvg width={150} height={150} role="img" aria-label="Void" />
        }
      />
    );
  }

  let player: React.ReactNode;
  if (framesQuery.isError) {
    player = (
      <ErrorMessage
        text="Error loading timelapse frames"
        subtext={framesQuery.error.message}
      />
    );
  } else if (framesQuery.isPending) {
    player = <Loading text="Loading frames" fullScreen={false} />;
  } else if (framesQuery.data.frames.length === 0) {
    player = (
      <Typography align="center" color="text.secondary" sx={{ padding: 4 }}>
        No timelapse frames in this range
      </Typography>
    );
  } else if (framesQuery.data.stream === null) {
    player = (
      <Typography align="center" color="text.secondary" sx={{ padding: 4 }}>
        The timelapse frames in this range could not be read
      </Typography>
    );
  } else {
    player = (
      <TimelapsePlayer
        // Start from the beginning when another range is selected
        key={`${range.start}-${range.end}-${density}`}
        camera_identifier={camera_identifier}
        frames={framesQuery.data.frames}
        step={framesQuery.data.step}
        stream={framesQuery.data.stream}
      />
    );
  }

  const renderActive = isRenderActive(render.state);

  return (
    <Container sx={{ paddingX: { xs: 1, md: 2 }, paddingY: 1 }}>
      <Stack spacing={2}>
        <Stack
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          spacing={1}
        >
          <Typography variant="h5">{cameraQuery.data.name}</Typography>
          <Button
            variant="contained"
            startIcon={
              renderActive ? (
                <CircularProgress size={16} color="inherit" />
              ) : (
                <VideoAdd size={20} />
              )
            }
            disabled={
              !renderActive &&
              (!framesQuery.data || framesQuery.data.total === 0)
            }
            onClick={() => {
              render.show();
              setRenderOpen(true);
            }}
          >
            {renderActive ? "Rendering" : "Render Video"}
          </Button>
        </Stack>
        <TimelapseRangeSelector
          camera_identifier={camera_identifier}
          selection={selection}
          range={range}
          density={density}
          onSelectionChange={setSelection}
          onDensityChange={setDensity}
        />
        <Paper variant="outlined" sx={{ overflow: "hidden" }}>
          {player}
        </Paper>
        {framesQuery.data && framesQuery.data.step ? (
          <Typography variant="caption" color="text.secondary">
            Showing {framesQuery.data.frames.length} of {framesQuery.data.total}{" "}
            frames, one every {framesQuery.data.step} seconds
          </Typography>
        ) : null}
      </Stack>
      {framesQuery.data ? (
        <TimelapseRenderDialog
          open={renderOpen}
          onClose={() => setRenderOpen(false)}
          camera_identifier={camera_identifier}
          start={framesQuery.data.start}
          end={framesQuery.data.end}
          total={framesQuery.data.total}
          render={render}
        />
      ) : null}
    </Container>
  );
}

export default CameraTimelapse;
