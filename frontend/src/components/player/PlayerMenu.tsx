import { GlobalFilters } from "@carbon/icons-react";
import Checkbox from "@mui/material/Checkbox";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import MenuItem from "@mui/material/MenuItem";
import React from "react";
import { useShallow } from "zustand/react/shallow";

import { CustomFab } from "components/player/CustomControls";
import { usePlayerSettingsStore } from "components/player/UsePlayerSettingsStore";
import * as types from "lib/types";

interface PlayerMenuProps {
  onMenuOpen: (event: React.MouseEvent<HTMLElement>) => void;
}

export function PlayerMenu({ onMenuOpen }: PlayerMenuProps) {
  return (
    <CustomFab onClick={onMenuOpen}>
      <GlobalFilters />
    </CustomFab>
  );
}

interface PlayerMenuItemsProps {
  camera: types.Camera | types.FailedCamera;
}

export function PlayerMenuItems({ camera }: PlayerMenuItemsProps) {
  const {
    mjpegPlayer,
    setMjpegPlayer,
    drawObjects,
    setDrawObjects,
    drawMotion,
    setDrawMotion,
    drawObjectMask,
    setDrawObjectMask,
    drawMotionMask,
    setDrawMotionMask,
    drawZones,
    setDrawZones,
    drawPostProcessorMask,
    setDrawPostProcessorMask,
  } = usePlayerSettingsStore(
    useShallow((state) => ({
      // mjpegPlayer defaults to true if live_stream_available is false, otherwise false
      mjpegPlayer: !camera.live_stream_available
        ? true
        : (state.mjpegPlayerMap[camera.identifier] ?? false),
      setMjpegPlayer: state.setMjpegPlayer,
      drawObjects: state.drawObjectsMap[camera.identifier] ?? false,
      setDrawObjects: state.setDrawObjects,
      drawMotion: state.drawMotionMap[camera.identifier] ?? false,
      setDrawMotion: state.setDrawMotion,
      drawObjectMask: state.drawObjectMaskMap[camera.identifier] ?? false,
      setDrawObjectMask: state.setDrawObjectMask,
      drawMotionMask: state.drawMotionMaskMap[camera.identifier] ?? false,
      setDrawMotionMask: state.setDrawMotionMask,
      drawZones: state.drawZonesMap[camera.identifier] ?? false,
      setDrawZones: state.setDrawZones,
      drawPostProcessorMask:
        state.drawPostProcessorMaskMap[camera.identifier] ?? false,
      setDrawPostProcessorMask: state.setDrawPostProcessorMask,
    })),
  );

  return (
    <>
      <MenuItem
        onClick={() => {
          setMjpegPlayer(camera.identifier, !mjpegPlayer);
        }}
        disabled={!camera.live_stream_available}
      >
        <ListItemIcon>
          <Checkbox checked={mjpegPlayer} />
        </ListItemIcon>
        <ListItemText id="toggle-player-type" primary="Use MJPEG Player" />
      </MenuItem>
      <MenuItem
        onClick={() => {
          setDrawObjects(camera.identifier, !drawObjects);
          if (!drawObjects) {
            setMjpegPlayer(camera.identifier, true);
          }
        }}
        disabled={!mjpegPlayer}
        sx={{ ml: 3 }}
      >
        <ListItemIcon sx={{ minWidth: 0, mr: 1 }}>
          <Checkbox checked={drawObjects} />
        </ListItemIcon>
        <ListItemText id="draw-objects" primary="Draw objects" />
      </MenuItem>
      <MenuItem
        onClick={() => {
          setDrawMotion(camera.identifier, !drawMotion);
          if (!drawMotion) {
            setMjpegPlayer(camera.identifier, true);
          }
        }}
        disabled={!mjpegPlayer}
        sx={{ ml: 3 }}
      >
        <ListItemIcon sx={{ minWidth: 0, mr: 1 }}>
          <Checkbox checked={drawMotion} />
        </ListItemIcon>
        <ListItemText id="draw-motion" primary="Draw motion" />
      </MenuItem>
      <MenuItem
        onClick={() => {
          setDrawObjectMask(camera.identifier, !drawObjectMask);
          if (!drawObjectMask) {
            setMjpegPlayer(camera.identifier, true);
          }
        }}
        disabled={!mjpegPlayer}
        sx={{ ml: 3 }}
      >
        <ListItemIcon sx={{ minWidth: 0, mr: 1 }}>
          <Checkbox checked={drawObjectMask} />
        </ListItemIcon>
        <ListItemText id="draw-object-mask" primary="Draw object mask" />
      </MenuItem>
      <MenuItem
        onClick={() => {
          setDrawMotionMask(camera.identifier, !drawMotionMask);
          if (!drawMotionMask) {
            setMjpegPlayer(camera.identifier, true);
          }
        }}
        disabled={!mjpegPlayer}
        sx={{ ml: 3 }}
      >
        <ListItemIcon sx={{ minWidth: 0, mr: 1 }}>
          <Checkbox checked={drawMotionMask} />
        </ListItemIcon>
        <ListItemText id="draw-motion-mask" primary="Draw motion mask" />
      </MenuItem>
      <MenuItem
        onClick={() => {
          setDrawZones(camera.identifier, !drawZones);
          if (!drawZones) {
            setMjpegPlayer(camera.identifier, true);
          }
        }}
        disabled={!mjpegPlayer}
        sx={{ ml: 3 }}
      >
        <ListItemIcon sx={{ minWidth: 0, mr: 1 }}>
          <Checkbox checked={drawZones} />
        </ListItemIcon>
        <ListItemText id="draw-zones" primary="Draw zones" />
      </MenuItem>
      <MenuItem
        onClick={() => {
          setDrawPostProcessorMask(camera.identifier, !drawPostProcessorMask);
          if (!drawPostProcessorMask) {
            setMjpegPlayer(camera.identifier, true);
          }
        }}
        disabled={!mjpegPlayer}
        sx={{ ml: 3 }}
      >
        <ListItemIcon sx={{ minWidth: 0, mr: 1 }}>
          <Checkbox checked={drawPostProcessorMask} />
        </ListItemIcon>
        <ListItemText
          id="draw-post-processor-mask"
          primary="Draw post processor mask"
        />
      </MenuItem>
    </>
  );
}
