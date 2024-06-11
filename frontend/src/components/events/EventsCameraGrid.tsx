import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Grid from "@mui/material/Grid";
import Grow from "@mui/material/Grow";
import { useTheme } from "@mui/material/styles";
import { useEffect, useRef } from "react";

import { CameraCard } from "components/camera/CameraCard";
import { COLUMN_HEIGHT } from "components/events/utils";
import * as types from "lib/types";

const useResizeObserver = (
  divRef: React.RefObject<HTMLDivElement>,
  playerCardRef: React.RefObject<HTMLDivElement> | undefined,
) => {
  const theme = useTheme();
  const resizeObserver = useRef<ResizeObserver>();

  useEffect(() => {
    if (!divRef.current || !playerCardRef || !playerCardRef.current) {
      return () => {};
    }

    resizeObserver.current = new ResizeObserver(() => {
      if (!divRef.current || !playerCardRef.current) {
        return;
      }

      divRef.current.style.maxHeight = `calc(${COLUMN_HEIGHT} - ${theme.headerHeight}px - ${theme.margin} - ${playerCardRef.current.offsetHeight}px)`;
    });

    resizeObserver.current.observe(playerCardRef.current);

    return () => {
      if (resizeObserver.current) {
        resizeObserver.current.disconnect();
      }
    };
  }, [divRef, playerCardRef, theme.headerHeight, theme.margin]);
};

type CameraGridProps = {
  cameras: types.CamerasOrFailedCameras;
  changeSelectedCamera: (
    ev: React.MouseEvent<HTMLButtonElement, MouseEvent>,
    camera: types.Camera | types.FailedCamera,
  ) => void;
  selectedCamera: types.Camera | types.FailedCamera | null;
};
function CameraGrid({
  cameras,
  changeSelectedCamera,
  selectedCamera,
}: CameraGridProps) {
  const theme = useTheme();

  return (
    <Grid container spacing={0.5}>
      {cameras
        ? Object.keys(cameras)
            .sort()
            .map((camera_identifier) => (
              <Grow in appear key={camera_identifier}>
                <Grid
                  item
                  xs={12}
                  sm={12}
                  md={6}
                  lg={6}
                  xl={4}
                  key={camera_identifier}
                >
                  <CameraCard
                    camera_identifier={camera_identifier}
                    compact
                    buttons={false}
                    onClick={changeSelectedCamera}
                    border={
                      selectedCamera &&
                      camera_identifier === selectedCamera.identifier
                        ? `2px solid ${theme.palette.primary[400]}`
                        : "2px solid transparent"
                    }
                  />
                </Grid>
              </Grow>
            ))
        : null}
    </Grid>
  );
}

type EventsCameraGridPropsCard = {
  variant: "card";
  playerCardRef: React.RefObject<HTMLDivElement>;
  cameras: types.CamerasOrFailedCameras;
  changeSelectedCamera: (
    ev: React.MouseEvent<HTMLButtonElement, MouseEvent>,
    camera: types.Camera | types.FailedCamera,
  ) => void;
  selectedCamera: types.Camera | types.FailedCamera | null;
};
type EventsCameraGridPropsGrid = {
  variant?: "grid";
  cameras: types.CamerasOrFailedCameras;
  changeSelectedCamera: (
    ev: React.MouseEvent<HTMLButtonElement, MouseEvent>,
    camera: types.Camera | types.FailedCamera,
  ) => void;
  selectedCamera: types.Camera | types.FailedCamera | null;
};
type EventsCameraGridProps =
  | EventsCameraGridPropsCard
  | EventsCameraGridPropsGrid;
export function EventsCameraGrid(props: EventsCameraGridProps) {
  const {
    variant = "card",
    cameras,
    changeSelectedCamera,
    selectedCamera,
  } = props;

  const playerCardRef =
    variant === "card"
      ? (props as EventsCameraGridPropsCard).playerCardRef
      : undefined;

  const ref = useRef<HTMLDivElement>(null);
  useResizeObserver(ref, playerCardRef);

  if (variant === "grid") {
    return (
      <CameraGrid
        cameras={cameras}
        changeSelectedCamera={changeSelectedCamera}
        selectedCamera={selectedCamera}
      />
    );
  }
  return (
    <Card
      ref={ref}
      variant="outlined"
      sx={{
        overflow: "auto",
        overflowX: "hidden",
      }}
    >
      <CardContent sx={{ padding: 0 }}>
        <CameraGrid
          cameras={cameras}
          changeSelectedCamera={changeSelectedCamera}
          selectedCamera={selectedCamera}
        />
      </CardContent>
    </Card>
  );
}
