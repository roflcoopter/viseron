import Tooltip from "@mui/material/Tooltip";
import { useTheme } from "@mui/material/styles";
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
    const theme = useTheme();

    if (active && cameraEvent) {
      return (
        <Tooltip
          placement="left"
          arrow
          title={
            <div>
              <div>{`Event: ${cameraEvent.type}`}</div>
              <div>{`Start: ${new Date(
                cameraEvent.start_time,
              ).toLocaleString()}`}</div>
              {cameraEvent.end_time ? (
                <div>{`End:   ${new Date(
                  cameraEvent.end_time,
                ).toLocaleString()}`}</div>
              ) : null}
            </div>
          }
        >
          <div
            className={variant || undefined}
            style={{
              height: TICK_HEIGHT,
              minWidth: "6px",
              background: `linear-gradient(${
                theme.palette[cameraEvent.type]
              }, ${theme.palette[cameraEvent.type]}) no-repeat center/6px 100%`,
              ...(variant === "first" && {
                borderTopLeftRadius: "40%",
                borderTopRightRadius: "40%",
              }),
              ...(variant === "last" && {
                borderBottomLeftRadius: "40%",
                borderBottomRightRadius: "40%",
              }),
              ...(variant === "middle" && {
                borderRadius: "0",
              }),
              ...(variant === "round" && {
                borderRadius: "40%",
              }),
              overflow: "hidden",
            }}
          />
        </Tooltip>
      );
    }
    return (
      <div
        className={variant || undefined}
        style={{
          height: TICK_HEIGHT,
          width: "6px",
          background: `linear-gradient(${theme.palette.divider}, ${theme.palette.divider}) no-repeat center/1px 100%`,
        }}
      />
    );
  },
);
