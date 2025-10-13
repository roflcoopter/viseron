import Box from "@mui/material/Box";
import Grid from "@mui/material/Grid2";
import { useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import {
  type JSX,
  forwardRef,
  useCallback,
  useImperativeHandle,
  useRef,
} from "react";

import {
  GridLayout,
  setPlayerSize,
  useGridLayout,
} from "components/player/grid/utils";
import * as types from "lib/types";

type PlayerItemProps = {
  camera: types.Camera | types.FailedCamera;
  containerRef: React.RefObject<HTMLDivElement | null>;
  gridLayout: GridLayout;
  renderPlayer: (
    camera: types.Camera | types.FailedCamera,
    playerRef: React.RefObject<any>,
  ) => JSX.Element;
  forceBreakpoint?: boolean;
};
const PlayerItem = forwardRef<PlayerItemRef, PlayerItemProps>(
  (
    { camera, containerRef, gridLayout, renderPlayer, forceBreakpoint },
    ref,
  ) => {
    const theme = useTheme();
    const _smBreakpoint = useMediaQuery(theme.breakpoints.up("sm"));
    const smBreakpoint =
      forceBreakpoint !== undefined ? forceBreakpoint : _smBreakpoint;
    const boxRef = useRef<HTMLDivElement>(null);
    const playerRef = useRef<any>(null);

    useImperativeHandle(ref, () => ({
      // PlayerGrid will call this function to set the size of the player.
      // Done this way since the player size depends on the size of the parent
      // which is not known until the parent has been rendered
      setSize: () => {
        setPlayerSize(containerRef, boxRef, camera, gridLayout, smBreakpoint);
      },
    }));

    return (
      <Grid
        key={camera.identifier}
        sx={{
          flexBasis: "min-content",
        }}
        size={12 / gridLayout.columns}
      >
        <Box
          ref={boxRef}
          sx={{
            position: "relative",
          }}
        >
          {renderPlayer(camera, playerRef)}
        </Box>
      </Grid>
    );
  },
);

export interface PlayerItemRef {
  setSize: () => void;
}

type PlayerGridProps = {
  cameras: types.CamerasOrFailedCameras;
  containerRef: React.RefObject<HTMLDivElement | null>;
  renderPlayer: (
    camera: types.Camera | types.FailedCamera,
    playerRef: React.RefObject<any>,
  ) => JSX.Element;
  forceBreakpoint?: boolean;
};
export const PlayerGrid = ({
  cameras,
  containerRef,
  renderPlayer,
  forceBreakpoint,
}: PlayerGridProps) => {
  const playerItemRefs = useRef<(PlayerItemRef | null)[]>([]);
  const setPlayerItemRef = (index: number, ref: PlayerItemRef | null) => {
    playerItemRefs.current[index] = ref;
  };

  const setPlayerItemsSize = useCallback(() => {
    playerItemRefs.current.forEach((playerItemRef) => {
      if (playerItemRef) {
        playerItemRef.setSize();
      }
    });
  }, [playerItemRefs]);

  const gridLayout = useGridLayout(containerRef, cameras, setPlayerItemsSize);

  return (
    <Grid
      container
      spacing={0}
      sx={{ height: "100%" }}
      alignContent="center"
      justifyContent="center"
    >
      {Object.values(cameras).map((camera, index) => (
        <PlayerItem
          ref={(node) => {
            setPlayerItemRef(index, node);
          }}
          key={camera.identifier}
          camera={camera}
          containerRef={containerRef}
          gridLayout={gridLayout}
          renderPlayer={renderPlayer}
          forceBreakpoint={forceBreakpoint}
        />
      ))}
    </Grid>
  );
};
