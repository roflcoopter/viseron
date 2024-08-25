import Image from "@jy95/material-ui-image";
import Box from "@mui/material/Box";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import { useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import { useCallback, useEffect, useRef, useState } from "react";

import { CameraNameOverlay } from "components/camera/CameraNameOverlay";
import { TimelinePlayer } from "components/events/timeline/TimelinePlayer";
import {
  getSrc,
  playerCardSmMaxHeight,
  useFilteredCameras,
} from "components/events/utils";
import { useResizeObserver } from "hooks/UseResizeObserver";
import * as types from "lib/types";

dayjs.extend(utc);

type GridLayout = {
  columns: number;
  rows: number;
};

// Dont fully understand why we need to subtract 4 from the height
// to keep the players from overflowing the paper
const getContainerHeight = (
  paperRef: React.RefObject<HTMLDivElement>,
  smBreakpoint: boolean,
) =>
  smBreakpoint
    ? paperRef.current?.clientHeight || 0
    : playerCardSmMaxHeight() -
      ((paperRef.current?.offsetHeight || 0) -
        (paperRef.current?.clientHeight || 0)) -
      4;

const calculateCellDimensions = (
  paperRef: React.RefObject<HTMLDivElement>,
  camera: types.Camera | types.FailedCamera,
  gridLayout: GridLayout,
  smBreakpoint: boolean,
) => {
  const containerWidth = paperRef.current?.clientWidth || 0;
  const containerHeight = getContainerHeight(paperRef, smBreakpoint);
  const cellWidth = containerWidth / gridLayout.columns;
  const cellHeight = containerHeight / gridLayout.rows;
  const cameraAspectRatio = camera.width / camera.height;
  const cellAspectRatio = cellWidth / cellHeight;

  if (cameraAspectRatio > cellAspectRatio) {
    // Video is wider than the cell, fit to width
    const width = cellWidth;
    const height = cellWidth / cameraAspectRatio;
    return { width, height };
  }
  // Video is taller than the cell, fit to height
  const height = cellHeight;
  const width = cellHeight * cameraAspectRatio;
  return { width, height };
};

const calculateLayout = (
  paperRef: React.RefObject<HTMLDivElement>,
  cameras: types.CamerasOrFailedCameras,
  smBreakpoint: boolean,
) => {
  if (!paperRef.current) return { columns: 1, rows: 1 };

  const containerWidth = paperRef.current.clientWidth;
  const containerHeight = getContainerHeight(paperRef, smBreakpoint);

  let bestLayout = { columns: 1, rows: 1 };
  let bestCoverage = 0;
  const camerasLength = Object.keys(cameras).length;

  for (let columns = 1; columns <= camerasLength; columns++) {
    const rows = Math.ceil(camerasLength / columns);
    const cellWidth = containerWidth / columns;
    const cellHeight = containerHeight / rows;

    let totalCoverage = 0;
    Object.values(cameras).forEach((camera) => {
      const cameraCoverage = Math.min(
        cellWidth / (camera.width / camera.height) / cellHeight,
        (cellHeight * (camera.width / camera.height)) / cellWidth,
      );
      totalCoverage += cameraCoverage;
    });

    if (totalCoverage > bestCoverage) {
      bestCoverage = totalCoverage;
      bestLayout = { columns, rows };
    }
  }

  return bestLayout;
};

const useGridLayout = (
  paperRef: React.RefObject<HTMLDivElement>,
  cameras: types.CamerasOrFailedCameras,
) => {
  const theme = useTheme();
  const smBreakpoint = useMediaQuery(theme.breakpoints.up("sm"));
  const [gridLayout, setGridLayout] = useState<{
    columns: number;
    rows: number;
  }>({ columns: 1, rows: 1 });

  const handleResize = useCallback(() => {
    const layout = calculateLayout(paperRef, cameras, smBreakpoint);
    if (
      layout.columns !== gridLayout.columns ||
      layout.rows !== gridLayout.rows
    ) {
      setGridLayout(layout);
    }
  }, [cameras, gridLayout.columns, gridLayout.rows, paperRef, smBreakpoint]);

  // Observe both the paperRef and window resize to update the layout
  useResizeObserver(paperRef, handleResize);
  useEffect(() => {
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [handleResize]);

  return gridLayout;
};

const setPlayerSize = (
  paperRef: React.RefObject<HTMLDivElement>,
  boxRef: React.RefObject<HTMLDivElement>,
  camera: types.Camera | types.FailedCamera,
  gridLayout: GridLayout,
  smBreakpoint: boolean,
) => {
  if (paperRef.current && boxRef.current) {
    const { width, height } = calculateCellDimensions(
      paperRef,
      camera,
      gridLayout,
      smBreakpoint,
    );
    boxRef.current.style.width = `${width}px`;
    boxRef.current.style.height = `${height}px`;
  }
};

// Set player size based on paper size and grid layout
const useSetPlayerSize = (
  paperRef: React.RefObject<HTMLDivElement>,
  boxRef: React.RefObject<HTMLDivElement>,
  camera: types.Camera | types.FailedCamera,
  gridLayout: GridLayout,
) => {
  const theme = useTheme();
  const smBreakpoint = useMediaQuery(theme.breakpoints.up("sm"));

  // Set size
  // Can't use useLayoutEffect since the paperRef is not ready
  useEffect(() => {
    setPlayerSize(paperRef, boxRef, camera, gridLayout, smBreakpoint);
  }, [boxRef, camera, paperRef, gridLayout, smBreakpoint]);

  // Resize on window resize
  useEffect(() => {
    const handleResize = () => {
      setPlayerSize(paperRef, boxRef, camera, gridLayout, smBreakpoint);
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [boxRef, camera, paperRef, gridLayout, smBreakpoint]);
};

type PlayerItemProps = {
  camera: types.Camera | types.FailedCamera;
  paperRef: React.RefObject<HTMLDivElement>;
  requestedTimestamp: number;
  gridLayout: GridLayout;
};
const PlayerItem = ({
  camera,
  paperRef,
  requestedTimestamp,
  gridLayout,
}: PlayerItemProps) => {
  const boxRef = useRef<HTMLDivElement>(null);
  useSetPlayerSize(paperRef, boxRef, camera, gridLayout);

  return (
    <Grid
      item
      xs={12 / gridLayout.columns}
      key={camera.identifier}
      sx={{
        display: "flex",
        justifyContent: "center",
        alignContent: "center",
        alignItems: "end",
      }}
    >
      <Box
        ref={boxRef}
        sx={{
          width: "100%",
          height: "100%",
          position: "relative",
        }}
      >
        <TimelinePlayer
          key={camera.identifier}
          camera={camera}
          requestedTimestamp={requestedTimestamp}
        />
        <CameraNameOverlay camera_identifier={camera.identifier} />
      </Box>
    </Grid>
  );
};

type PlayerGridProps = {
  cameras: types.CamerasOrFailedCameras;
  paperRef: React.RefObject<HTMLDivElement>;
  requestedTimestamp: number;
  gridLayout: GridLayout;
};
const PlayerGrid = ({
  cameras,
  paperRef,
  requestedTimestamp,
  gridLayout,
}: PlayerGridProps) => (
  <Grid
    container
    spacing={0}
    sx={{ height: "100%" }}
    alignContent="center"
    justifyContent="center"
  >
    {Object.values(cameras).map((camera) => (
      <PlayerItem
        key={camera.identifier}
        camera={camera}
        paperRef={paperRef}
        requestedTimestamp={requestedTimestamp}
        gridLayout={gridLayout}
      />
    ))}
  </Grid>
);

type PlayerCardProps = {
  cameras: types.CamerasOrFailedCameras;
  selectedEvent: types.CameraEvent | null;
  requestedTimestamp: number | null;
  selectedTab: "events" | "timeline";
};
export const PlayerCard = ({
  cameras,
  selectedEvent,
  requestedTimestamp,
}: PlayerCardProps) => {
  const theme = useTheme();
  const paperRef = useRef<HTMLDivElement>(null);
  const filteredCameras = useFilteredCameras(cameras);
  const gridLayout = useGridLayout(paperRef, filteredCameras);

  const camera = selectedEvent
    ? cameras[selectedEvent.camera_identifier]
    : null;
  const src = camera && selectedEvent ? getSrc(selectedEvent) : undefined;

  return (
    <Paper
      ref={paperRef}
      variant="outlined"
      sx={{
        position: "relative",
        width: "100%",
        height: "100%",
        boxSizing: "content-box",
      }}
    >
      {requestedTimestamp ? (
        <PlayerGrid
          cameras={filteredCameras}
          paperRef={paperRef}
          requestedTimestamp={requestedTimestamp}
          gridLayout={gridLayout}
        />
      ) : (
        src &&
        camera && (
          <>
            <Image
              src={src}
              aspectRatio={camera.width / camera.height}
              color={theme.palette.background.default}
              animationDuration={1000}
              imageStyle={{
                objectFit: "contain",
              }}
            />
            <CameraNameOverlay camera_identifier={camera.identifier} />
          </>
        )
      )}
    </Paper>
  );
};
