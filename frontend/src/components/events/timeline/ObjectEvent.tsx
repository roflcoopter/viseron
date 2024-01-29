import Image from "@jy95/material-ui-image";
import DirectionsCarIcon from "@mui/icons-material/DirectionsCar";
import ImageSearchIcon from "@mui/icons-material/ImageSearch";
import PersonIcon from "@mui/icons-material/Person";
import Box from "@mui/material/Box";
import Tooltip from "@mui/material/Tooltip";
import { useTheme } from "@mui/material/styles";
// eslint-disable-next-line import/no-extraneous-dependencies
import { Instance } from "@popperjs/core";
import { memo, useRef, useState } from "react";

import * as types from "lib/types";

import { TICK_HEIGHT } from "./TimelineTable";

const labelToIcon = (label: string) => {
  switch (label) {
    case "person":
      return PersonIcon;
    case "car" || "truck" || "vehicle":
      return DirectionsCarIcon;
    default:
      return ImageSearchIcon;
  }
};

const Divider = ({ boxRef }: { boxRef?: React.Ref<HTMLDivElement> }) => (
  <Box
    ref={boxRef}
    sx={(theme) => ({
      height: "1px",
      flexGrow: 1,
      backgroundColor: theme.palette.divider,
    })}
  />
);

const DetectionDetails = ({
  objectEvent,
  boxRef,
}: {
  objectEvent: types.CameraObjectEvent;
  boxRef?: React.Ref<HTMLDivElement>;
}) => {
  const Icon = labelToIcon(objectEvent.label);
  return (
    <Box ref={boxRef} color="primary" sx={{ height: "25px", width: "25px" }}>
      <Icon color="primary" />
    </Box>
  );
};

const DetectionSnapshot = ({
  objectEvent,
  eventIndex,
  scale,
}: {
  objectEvent: types.CameraObjectEvent;
  eventIndex: number;
  scale: number;
}) => {
  const theme = useTheme();
  return (
    <Box
      sx={{
        width: scale > 1 ? "70%" : "35%",
        margin: "auto",
        marginLeft: eventIndex % 2 === 0 ? "20px" : "10px",
        marginRight: eventIndex % 2 === 0 ? "10px" : "20px",
        overflow: "hidden",
        borderRadius: "5px",
        border: `1px solid ${
          theme.palette.mode === "dark"
            ? theme.palette.primary[900]
            : theme.palette.primary[200]
        }`,
        transform: `translateY(calc(-50% + ${TICK_HEIGHT / 2}px))`,
        transition: "width 0.15s ease-in-out",
      }}
    >
      <Image
        src={objectEvent.snapshot_path}
        color={theme.palette.background.default}
        animationDuration={1000}
      />
    </Box>
  );
};

type ObjectEventProps = {
  objectEvent: types.CameraObjectEvent;
  eventIndex: number;
};
export const ObjectEvent = memo(
  ({ objectEvent, eventIndex }: ObjectEventProps) => {
    const [scale, setScale] = useState(1);
    const popperRef = useRef<Instance>(null);
    const tooltipAnchor = useRef<HTMLDivElement>(null);
    const date = new Date(objectEvent.time);

    return (
      <Tooltip
        arrow
        title={
          <Box>
            <Box>{`Label: ${objectEvent.label}`}</Box>
            <Box>{`Confidence: ${objectEvent.confidence}`}</Box>
            <Box>{`Timestamp: ${date.toLocaleString()}`}</Box>
          </Box>
        }
        PopperProps={{
          popperRef,
          anchorEl: tooltipAnchor.current,
        }}
      >
        <Box
          onMouseEnter={() => {
            setScale(1.05);
          }}
          onMouseLeave={() => setScale(1)}
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            height: TICK_HEIGHT,
            width: "100%",
          }}
        >
          <Divider />
          <DetectionDetails boxRef={tooltipAnchor} objectEvent={objectEvent} />
          <Divider />
          <DetectionSnapshot
            objectEvent={objectEvent}
            eventIndex={eventIndex}
            scale={scale}
          />
        </Box>
      </Tooltip>
    );
  },
);
