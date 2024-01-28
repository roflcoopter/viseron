import Box from "@mui/material/Box";
import Tooltip from "@mui/material/Tooltip";
import { memo } from "react";

import * as types from "lib/types";

import { TICK_HEIGHT } from "./TimelineTable";

type ActivityLinePropsActive = {
  active: boolean;
  cameraEvent: types.CameraMotionEvent | types.CameraRecordingEvent | null;
  variant: "first" | "middle" | "last" | "round" | null;
};
type ActivityLinePropsInactive = {
  active: boolean;
  cameraEvent: null;
  variant: null;
};
export type ActivityLineProps =
  | ActivityLinePropsActive
  | ActivityLinePropsInactive;

export const ActivityLine = memo(
  ({ active, cameraEvent, variant }: ActivityLineProps) => {
    if (active && cameraEvent) {
      const borderTopLeftRadius = variant === "first" ? "40%" : undefined;
      const borderTopRightRadius = variant === "first" ? "40%" : undefined;
      const borderBottomLeftRadius = variant === "last" ? "40%" : undefined;
      const borderBottomRightRadius = variant === "last" ? "40%" : undefined;
      const borderRadius = variant === "round" ? "40%" : undefined;
      return (
        <Tooltip
          placement="left"
          arrow
          title={
            <Box>
              <Box>{`Event: ${cameraEvent.type}`}</Box>
              <Box>{`Start: ${new Date(
                cameraEvent.start_time,
              ).toLocaleString()}`}</Box>
              {cameraEvent.end_time ? (
                <Box>{`End:   ${new Date(
                  cameraEvent.end_time,
                ).toLocaleString()}`}</Box>
              ) : null}
            </Box>
          }
        >
          <Box sx={{ width: "6px" }}>
            <Box
              sx={(theme) => ({
                height: TICK_HEIGHT,
                width: "6px",
                margin: "auto",
                backgroundColor: theme.palette[cameraEvent.type],
                borderRadius,
                borderTopLeftRadius,
                borderTopRightRadius,
                borderBottomLeftRadius,
                borderBottomRightRadius,
              })}
            />
          </Box>
        </Tooltip>
      );
    }
    return (
      <Box sx={{ width: "6px" }}>
        <Box
          sx={(theme) => ({
            margin: "auto",
            height: TICK_HEIGHT,
            width: "2px",
            backgroundColor: theme.palette.divider,
          })}
        />
      </Box>
    );
  },
);
