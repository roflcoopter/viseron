import {
  CenterSquare,
  ErrorOutline,
  Help,
  Information,
} from "@carbon/icons-react";
import {
  Box,
  Button,
  CircularProgress,
  FormControl,
  Slider,
  Tooltip,
  Typography,
} from "@mui/material";
import { useState } from "react";

import { GrowingSpinner } from "components/loading/GrowingSpinner";
import { useToast } from "hooks/UseToast";
import {
  useMoveFocusImaging,
  useStopFocusImaging,
} from "lib/api/actions/onvif/imaging";

interface ImagingMoveProps {
  cameraIdentifier: string;
  imagingMoveOptions?: any;
  onSettingsApplied?: () => void;
}

export function ImagingMove({
  cameraIdentifier,
  imagingMoveOptions,
  onSettingsApplied,
}: ImagingMoveProps) {
  const toast = useToast();

  // Absolute move state
  const absoluteDefaults = {
    position:
      imagingMoveOptions?.Absolute?.Position?.Min !== undefined &&
      imagingMoveOptions?.Absolute?.Position?.Max !== undefined
        ? (imagingMoveOptions.Absolute.Position.Min +
            imagingMoveOptions.Absolute.Position.Max) /
          2
        : 0,
    speed:
      imagingMoveOptions?.Absolute?.Speed?.Min !== undefined &&
      imagingMoveOptions?.Absolute?.Speed?.Max !== undefined
        ? (imagingMoveOptions.Absolute.Speed.Min +
            imagingMoveOptions.Absolute.Speed.Max) /
          2
        : undefined,
  };
  const [userAbsolutePosition, setUserAbsolutePosition] = useState<
    number | null
  >(null);
  const [userAbsoluteSpeed, setUserAbsoluteSpeed] = useState<number | null>(
    null,
  );
  const absolutePosition = userAbsolutePosition ?? absoluteDefaults.position;
  const absoluteSpeed = userAbsoluteSpeed ?? absoluteDefaults.speed;

  // Relative move state
  const relativeDefaults = {
    distance:
      imagingMoveOptions?.Relative?.Distance?.Min !== undefined &&
      imagingMoveOptions?.Relative?.Distance?.Max !== undefined
        ? (imagingMoveOptions.Relative.Distance.Min +
            imagingMoveOptions.Relative.Distance.Max) /
          2
        : 0,
    speed:
      imagingMoveOptions?.Relative?.Speed?.Min !== undefined &&
      imagingMoveOptions?.Relative?.Speed?.Max !== undefined
        ? (imagingMoveOptions.Relative.Speed.Min +
            imagingMoveOptions.Relative.Speed.Max) /
          2
        : undefined,
  };
  const [userRelativeDistance, setUserRelativeDistance] = useState<
    number | null
  >(null);
  const [userRelativeSpeed, setUserRelativeSpeed] = useState<number | null>(
    null,
  );
  const relativeDistance = userRelativeDistance ?? relativeDefaults.distance;
  const relativeSpeed = userRelativeSpeed ?? relativeDefaults.speed;

  // Continuous move state
  const continuousDefaults = {
    speed:
      imagingMoveOptions?.Continuous?.Speed?.Min !== undefined &&
      imagingMoveOptions?.Continuous?.Speed?.Max !== undefined
        ? (imagingMoveOptions.Continuous.Speed.Min +
            imagingMoveOptions.Continuous.Speed.Max) /
          2
        : 0,
  };
  const [userContinuousSpeed, setUserContinuousSpeed] = useState<number | null>(
    null,
  );
  const continuousSpeed = userContinuousSpeed ?? continuousDefaults.speed;

  const [isMoving, setIsMoving] = useState<boolean>(false);
  const [isStopping, setIsStopping] = useState<boolean>(false);

  const moveFocusMutation = useMoveFocusImaging(cameraIdentifier);
  const stopFocusMutation = useStopFocusImaging(cameraIdentifier);

  const thumbWidth = 16;
  const halfThumb = thumbWidth / 2;

  const handleAbsoluteMove = () => {
    setIsMoving(true);
    const moveData: any = { Absolute: { Position: absolutePosition } };
    if (absoluteSpeed !== undefined) {
      moveData.Absolute.Speed = absoluteSpeed;
    }
    moveFocusMutation.mutate(moveData, {
      onSuccess: () => {
        toast.success("Absolute focus move executed successfully");
        setTimeout(() => onSettingsApplied?.(), 2000);
        setIsMoving(false);
      },
      onError: (err) => {
        toast.error(err?.message || "Failed to move focus");
        setIsMoving(false);
      },
    });
  };

  const handleRelativeMove = () => {
    if (relativeDistance === 0) return;

    setIsMoving(true);
    const moveData: any = { Relative: { Distance: relativeDistance } };
    if (relativeSpeed !== undefined) {
      moveData.Relative.Speed = relativeSpeed;
    }
    moveFocusMutation.mutate(moveData, {
      onSuccess: () => {
        toast.success("Relative focus move executed successfully");
        setTimeout(() => onSettingsApplied?.(), 2000);
        setIsMoving(false);
      },
      onError: (err) => {
        toast.error(err?.message || "Failed to move focus");
        setIsMoving(false);
      },
    });
  };

  const handleContinuousMove = () => {
    if (continuousSpeed === 0) return;

    setIsMoving(true);
    moveFocusMutation.mutate(
      { Continuous: { Speed: continuousSpeed } },
      {
        onSuccess: () => {
          toast.success("Continuous focus move executed successfully");
          setTimeout(() => onSettingsApplied?.(), 2000);
        },
        onError: (err) => {
          toast.error(err?.message || "Failed to move focus");
          setIsMoving(false);
        },
      },
    );
  };

  const handleStopFocus = () => {
    setIsStopping(true);
    stopFocusMutation.mutate(undefined, {
      onSuccess: () => {
        setIsStopping(false);
        toast.success("Focus move stopped successfully");
        setTimeout(() => onSettingsApplied?.(), 2000);
        setIsMoving(false);
      },
      onError: (err) => {
        toast.error(err?.message || "Failed to stop focus move");
        setIsStopping(false);
      },
    });
  };

  const renderSlider = (
    value: number,
    min: number,
    max: number,
    label: string,
    onChange: (value: number) => void,
    step: number = 0.1,
  ) => (
    <FormControl fullWidth>
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 0.5,
        }}
      >
        <Typography variant="caption">{label}</Typography>
        <Typography variant="caption" fontWeight="medium" color="primary">
          {value}
        </Typography>
      </Box>
      <Slider
        value={value}
        min={min}
        max={max}
        step={step}
        size="medium"
        color="primary"
        valueLabelDisplay="off"
        track={false}
        onChange={(_, newValue) => onChange(newValue as number)}
        sx={{
          width: `calc(100% - ${thumbWidth}px)`,
          ml: `${halfThumb}px`,
          "& .MuiSlider-rail": {
            transform: "scaleX(1.05)",
            top: "initial",
          },
          "& .MuiSlider-thumb": {
            height: thumbWidth,
            width: thumbWidth,
            borderRadius: "4px",
            "&:hover, &.Mui-focusVisible": {
              boxShadow: "0px 0px 0px 4px rgba(25, 118, 210, 0.16)",
            },
            "&:before": {
              boxShadow:
                "0px 0px 1px 0px rgba(0,0,0,0.2), 0px 0px 0px 0px rgba(0,0,0,0.14), 0px 0px 1px 0px rgba(0,0,0,0.12)",
            },
          },
          "& .MuiSlider-thumb.Mui-active": {
            boxShadow: "0px 0px 0px 8px rgba(25, 118, 210, 0.16)",
          },
        }}
      />
    </FormControl>
  );

  type MoveType = "Absolute" | "Relative" | "Continuous";

  const moveConfig: Record<
    MoveType,
    {
      title: string;
      tooltip: string;
      primaryKey: string;
      primaryLabel: string;
      primaryValue: number;
      primaryOnChange: (v: number) => void;
      speedValue?: number;
      speedOnChange?: (v: number) => void;
      handler: () => void;
      disableCondition: boolean;
    }
  > = {
    Absolute: {
      title: "Absolute Focus",
      tooltip:
        "Move focus to an absolute position. Position is the target position, Speed controls how fast to move there.",
      primaryKey: "Position",
      primaryLabel: "Position",
      primaryValue: absolutePosition,
      primaryOnChange: setUserAbsolutePosition,
      speedValue: absoluteSpeed,
      speedOnChange: setUserAbsoluteSpeed,
      handler: handleAbsoluteMove,
      disableCondition: isMoving,
    },
    Relative: {
      title: "Relative Focus",
      tooltip:
        "Move focus relative to current position. Distance is the offset (negative: near, positive: far), Speed controls how fast to move.",
      primaryKey: "Distance",
      primaryLabel: "Distance (negative: near, positive: far)",
      primaryValue: relativeDistance,
      primaryOnChange: setUserRelativeDistance,
      speedValue: relativeSpeed,
      speedOnChange: setUserRelativeSpeed,
      handler: handleRelativeMove,
      disableCondition: isMoving || relativeDistance === 0,
    },
    Continuous: {
      title: "Continuous Focus",
      tooltip:
        "Move focus continuously until stopped. Speed controls direction and velocity (negative: near, positive: far).",
      primaryKey: "Speed",
      primaryLabel: "Speed (negative: near, positive: far)",
      primaryValue: continuousSpeed,
      primaryOnChange: setUserContinuousSpeed,
      handler: handleContinuousMove,
      disableCondition: isMoving || continuousSpeed === 0,
    },
  };

  const renderControls = (type: MoveType, control: any) => {
    const config = moveConfig[type];
    const primaryMin = control?.[config.primaryKey]?.Min ?? 0;
    const primaryMax = control?.[config.primaryKey]?.Max ?? 1;
    const hasSpeed = type !== "Continuous" && control?.Speed?.Min !== undefined;
    const speedMin = control?.Speed?.Min ?? 0;
    const speedMax = control?.Speed?.Max ?? 1;

    return (
      <Box
        key={type}
        sx={{
          display: "flex",
          flexDirection: "column",
          gap: 1.5,
          border: 1,
          borderColor: "divider",
          borderRadius: 1,
          p: 1.5,
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
          <Tooltip title={config.tooltip} arrow placement="top">
            <Information size={16} />
          </Tooltip>
          <Typography variant="body2" sx={{ fontWeight: 500 }}>
            {config.title}
          </Typography>
        </Box>
        {renderSlider(
          config.primaryValue,
          primaryMin,
          primaryMax,
          config.primaryLabel,
          config.primaryOnChange,
        )}
        {hasSpeed &&
          config.speedOnChange &&
          renderSlider(
            config.speedValue ?? speedMin,
            speedMin,
            speedMax,
            "Speed",
            config.speedOnChange,
          )}
        <Box
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          gap={1}
        >
          <Button
            variant="contained"
            color="primary"
            fullWidth
            startIcon={
              isMoving ? (
                <GrowingSpinner color="primary.main" size={16} />
              ) : (
                <CenterSquare size={16} />
              )
            }
            onClick={config.handler}
            disabled={config.disableCondition}
          >
            {isMoving ? "Moving..." : "Move"}
          </Button>
          <Button
            variant="contained"
            color="error"
            fullWidth
            startIcon={
              isStopping ? (
                <CircularProgress enableTrackSlot size={16} />
              ) : (
                <ErrorOutline size={16} />
              )
            }
            onClick={handleStopFocus}
            disabled={!isMoving || isStopping}
          >
            Stop
          </Button>
        </Box>
      </Box>
    );
  };

  return (
    <Box>
      <Box
        display="flex"
        justifyContent="space-between"
        alignItems="center"
        mb={1.5}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Typography variant="subtitle2">Move Operations</Typography>
          <Tooltip
            title="The move command moves the focus lens in an absolute, a relative or in a continuous manner from its current position. Focus adjustments through this operation will turn off the autofocus."
            arrow
            placement="top"
          >
            <Help size={16} />
          </Tooltip>
        </Box>
      </Box>
      <Box display="flex" flexDirection="column" gap={1.5}>
        {(["Absolute", "Relative", "Continuous"] as MoveType[])
          .filter((type) => imagingMoveOptions?.[type])
          .map((type) => renderControls(type, imagingMoveOptions[type]))}
      </Box>
    </Box>
  );
}
