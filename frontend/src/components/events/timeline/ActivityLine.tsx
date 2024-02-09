import Tooltip from "@mui/material/Tooltip";
import { useTheme } from "@mui/material/styles";
import { memo } from "react";

import * as types from "lib/types";

import { TICK_HEIGHT } from "./TimelineTable";

function activityLineEqual(
  prevProps: ActivityLineProps,
  nextProps: ActivityLineProps,
) {
  return (
    prevProps.active === nextProps.active &&
    prevProps.cameraEvent?.type === nextProps.cameraEvent?.type &&
    prevProps.cameraEvent?.start_timestamp ===
      nextProps.cameraEvent?.start_timestamp &&
    prevProps.cameraEvent?.end_timestamp ===
      nextProps.cameraEvent?.end_timestamp &&
    prevProps.variant === nextProps.variant &&
    prevProps.availableTimespan === nextProps.availableTimespan
  );
}

type ActivityLinePropsActive = {
  active: boolean;
  cameraEvent: types.CameraMotionEvent | types.CameraRecordingEvent | null;
  variant: "first" | "middle" | "last" | "round" | null;
  availableTimespan: boolean;
};
type ActivityLinePropsInactive = {
  active: boolean;
  cameraEvent: null;
  variant: null;
  availableTimespan: boolean;
};
export type ActivityLineProps =
  | ActivityLinePropsActive
  | ActivityLinePropsInactive;

export const ActivityLine = memo(
  ({ active, cameraEvent, variant, availableTimespan }: ActivityLineProps) => {
    const theme = useTheme();

    const style = {
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
    };

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
              overflow: "hidden",
              transition: "background 0.5s",
              ...style,
            }}
          />
        </Tooltip>
      );
    }
    const background = availableTimespan
      ? theme.palette.primary[200]
      : theme.palette.divider;
    const thickness = availableTimespan ? 4 : 1;
    return (
      <div
        className={variant || undefined}
        style={{
          height: TICK_HEIGHT,
          width: "6px",
          flexShrink: 0,
          background: `linear-gradient(${background}, ${background}) no-repeat center/${thickness}px 100%`,
          transition: "background 0.2s linear",
          ...style,
        }}
      />
    );
  },
  activityLineEqual,
);
