import { ErrorOutline, Help, Information, Move } from "@carbon/icons-react";
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
  usePtzAbsoluteMove,
  usePtzContinuousMove,
  usePtzRelativeMove,
  usePtzStop,
} from "lib/api/actions/onvif/ptz";
import * as onvif_types from "lib/api/actions/onvif/types";
import * as types from "lib/types";

import { QueryWrapper } from "../../config/QueryWrapper";

interface PTZMovementsProps {
  cameraIdentifier: string;
  ptzNodes?: onvif_types.PtzNodesResponse;
  isLoading: boolean;
  isError: boolean;
  error: types.APIErrorResponse | null;
}

export function PTZMovements({
  cameraIdentifier,
  ptzNodes,
  isLoading,
  isError,
  error,
}: PTZMovementsProps) {
  const TITLE = "PTZ Movements";
  const DESC =
    "Control PTZ movements with supported capabilities. Some cameras may ignore the parameters defined here.";

  const toast = useToast();

  // ONVIF API hooks
  const continuousMoveMutation = usePtzContinuousMove();
  const relativeMoveMutation = usePtzRelativeMove();
  const absoluteMoveMutation = usePtzAbsoluteMove();
  const stopMutation = usePtzStop();

  // State for movement loading states
  const [isContinuousMoving, setIsContinuousMoving] = useState<boolean>(false);
  const [isContinuousStopping, setIsContinuousStopping] =
    useState<boolean>(false);
  const [isRelativeMoving, setIsRelativeMoving] = useState<boolean>(false);
  const [isRelativeStopping, setIsRelativeStopping] = useState<boolean>(false);
  const [isAbsoluteMoving, setIsAbsoluteMoving] = useState<boolean>(false);
  const [isAbsoluteStopping, setIsAbsoluteStopping] = useState<boolean>(false);

  // State for movements
  const [continuousPan, setContinuousPan] = useState<number>(0);
  const [continuousTilt, setContinuousTilt] = useState<number>(0);
  const [continuousZoom, setContinuousZoom] = useState<number>(0);

  const [relativePan, setRelativePan] = useState<number>(0);
  const [relativeTilt, setRelativeTilt] = useState<number>(0);
  const [relativeZoom, setRelativeZoom] = useState<number>(0);
  const [relativePanSpeed, setRelativePanSpeed] = useState<number | null>(null);
  const [relativeTiltSpeed, setRelativeTiltSpeed] = useState<number | null>(
    null,
  );
  const [relativeZoomSpeed, setRelativeZoomSpeed] = useState<number | null>(
    null,
  );

  const [absolutePan, setAbsolutePan] = useState<number>(0);
  const [absoluteTilt, setAbsoluteTilt] = useState<number>(0);
  const [absoluteZoom, setAbsoluteZoom] = useState<number>(0);
  const [absolutePanSpeed, setAbsolutePanSpeed] = useState<number | null>(null);
  const [absoluteTiltSpeed, setAbsoluteTiltSpeed] = useState<number | null>(
    null,
  );
  const [absoluteZoomSpeed, setAbsoluteZoomSpeed] = useState<number | null>(
    null,
  );

  if (!ptzNodes?.nodes || ptzNodes.nodes.length === 0) {
    return (
      <QueryWrapper
        isLoading={isLoading}
        isError={isError}
        errorMessage={
          error?.message || "Failed to load ptz movements information"
        }
        isEmpty
        emptyMessage="No ptz capabilities information available"
        title={TITLE}
      >
        <Box />
      </QueryWrapper>
    );
  }

  const firstNode = ptzNodes.nodes[0];
  const spaces = firstNode.SupportedPTZSpaces;

  if (!spaces) {
    return (
      <QueryWrapper
        isLoading={isLoading}
        isError={isError}
        errorMessage={
          error?.message || "Failed to load ptz movements information"
        }
        isEmpty
        emptyMessage="No PTZ spaces available"
        title={TITLE}
      >
        <Box />
      </QueryWrapper>
    );
  }

  const continuousPanTilt = spaces.ContinuousPanTiltVelocitySpace?.[0];
  const continuousZoomSpace = spaces.ContinuousZoomVelocitySpace?.[0];
  const relativePanTilt = spaces.RelativePanTiltTranslationSpace?.[0];
  const relativeZoomSpace = spaces.RelativeZoomTranslationSpace?.[0];
  const absolutePanTilt = spaces.AbsolutePanTiltPositionSpace?.[0];
  const absoluteZoomSpace = spaces.AbsoluteZoomPositionSpace?.[0];
  const panTiltSpeed = spaces.PanTiltSpeedSpace?.[0];
  const zoomSpeed = spaces.ZoomSpeedSpace?.[0];

  const thumbWidth = 16;
  const halfThumb = thumbWidth / 2;

  const handleContinuousMove = () => {
    if (continuousPan === 0 && continuousTilt === 0 && continuousZoom === 0)
      return;

    setIsContinuousMoving(true);
    continuousMoveMutation.mutate(
      {
        cameraIdentifier,
        params: {
          x_velocity: continuousPan,
          y_velocity: continuousTilt,
          zoom_velocity: continuousZoom,
        },
      },
      {
        onSuccess: () => {
          toast.success("Continuous move executed successfully");
        },
        onError: (err) => {
          toast.error(err?.message || "Failed to execute continuous move");
          setIsContinuousMoving(false);
        },
      },
    );
  };

  const handleRelativeMove = () => {
    if (relativePan === 0 && relativeTilt === 0 && relativeZoom === 0) return;

    setIsRelativeMoving(true);
    relativeMoveMutation.mutate(
      {
        cameraIdentifier,
        params: {
          x_translation: relativePan,
          y_translation: relativeTilt,
          zoom_translation: relativeZoom,
          x_speed: relativePanSpeed ?? undefined,
          y_speed: relativeTiltSpeed ?? undefined,
          zoom_speed: relativeZoomSpeed ?? undefined,
        },
      },
      {
        onSuccess: () => {
          toast.success("Relative move executed successfully");
          setIsRelativeMoving(false);
        },
        onError: (err) => {
          toast.error(err?.message || "Failed to execute relative move");
          setIsRelativeMoving(false);
        },
      },
    );
  };

  const handleAbsoluteMove = () => {
    setIsAbsoluteMoving(true);
    absoluteMoveMutation.mutate(
      {
        cameraIdentifier,
        params: {
          x_position: absolutePan,
          y_position: absoluteTilt,
          zoom_position: absoluteZoom,
          x_speed: absolutePanSpeed ?? undefined,
          y_speed: absoluteTiltSpeed ?? undefined,
          zoom_speed: absoluteZoomSpeed ?? undefined,
          is_adjusted: false,
        },
      },
      {
        onSuccess: () => {
          toast.success("Absolute move executed successfully");
          setIsAbsoluteMoving(false);
        },
        onError: (err) => {
          toast.error(err?.message || "Failed to execute absolute move");
          setIsAbsoluteMoving(false);
        },
      },
    );
  };

  const handleContinuousStop = () => {
    setIsContinuousStopping(true);
    stopMutation.mutate(
      { cameraIdentifier },
      {
        onSuccess: () => {
          toast.success("PTZ stopped successfully");
          setIsContinuousStopping(false);
          setIsContinuousMoving(false);
        },
        onError: (err) => {
          toast.error(err?.message || "Failed to stop PTZ");
          setIsContinuousStopping(false);
        },
      },
    );
  };

  const handleRelativeStop = () => {
    setIsRelativeStopping(true);
    stopMutation.mutate(
      { cameraIdentifier },
      {
        onSuccess: () => {
          toast.success("PTZ stopped successfully");
          setIsRelativeStopping(false);
          setIsRelativeMoving(false);
        },
        onError: (err) => {
          toast.error(err?.message || "Failed to stop PTZ");
          setIsRelativeStopping(false);
        },
      },
    );
  };

  const handleAbsoluteStop = () => {
    setIsAbsoluteStopping(true);
    stopMutation.mutate(
      { cameraIdentifier },
      {
        onSuccess: () => {
          toast.success("PTZ stopped successfully");
          setIsAbsoluteStopping(false);
          setIsAbsoluteMoving(false);
        },
        onError: (err) => {
          toast.error(err?.message || "Failed to stop PTZ");
          setIsAbsoluteStopping(false);
        },
      },
    );
  };

  const renderSlider = (
    value: number,
    min: number,
    max: number,
    label: string,
    onChange: (value: number) => void,
    step: number = 0.01,
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
          {value.toFixed(2)}
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

  return (
    <QueryWrapper
      isLoading={isLoading}
      isError={isError}
      errorMessage={
        error?.message || "Failed to load PTZ movements information"
      }
      isEmpty={!ptzNodes || ptzNodes.nodes.length === 0}
      emptyMessage="No PTZ capabilities information available"
      title={TITLE}
    >
      <Box>
        <Box
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          mb={1.5}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Typography variant="subtitle2">{TITLE}</Typography>
            <Tooltip title={DESC} arrow placement="top">
              <Help size={16} />
            </Tooltip>
          </Box>
        </Box>

        <Box display="flex" flexDirection="column" gap={1.5}>
          {/* Continuous Movement */}
          {(continuousPanTilt || continuousZoomSpace) && (
            <Box
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
              <Box display="flex" alignItems="center" gap={1}>
                <Tooltip
                  title="Move continuously at specified velocity. Values determine speed and direction (negative for opposite direction)."
                  arrow
                  placement="top"
                >
                  <Information size={16} />
                </Tooltip>
                <Typography variant="subtitle2">Continuous Move</Typography>
              </Box>
              {continuousPanTilt && (
                <>
                  {renderSlider(
                    continuousPan,
                    continuousPanTilt.XRange?.Min ?? -1,
                    continuousPanTilt.XRange?.Max ?? 1,
                    "Pan Velocity",
                    setContinuousPan,
                  )}
                  {renderSlider(
                    continuousTilt,
                    continuousPanTilt.YRange?.Min ?? -1,
                    continuousPanTilt.YRange?.Max ?? 1,
                    "Tilt Velocity",
                    setContinuousTilt,
                  )}
                </>
              )}
              {continuousZoomSpace &&
                renderSlider(
                  continuousZoom,
                  continuousZoomSpace.XRange?.Min ?? -1,
                  continuousZoomSpace.XRange?.Max ?? 1,
                  "Zoom Velocity",
                  setContinuousZoom,
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
                    isContinuousMoving ? (
                      <GrowingSpinner color="primary.main" size={16} />
                    ) : (
                      <Move size={16} />
                    )
                  }
                  onClick={handleContinuousMove}
                  disabled={
                    isContinuousMoving ||
                    isRelativeMoving ||
                    isAbsoluteMoving ||
                    (continuousPan === 0 &&
                      continuousTilt === 0 &&
                      continuousZoom === 0)
                  }
                >
                  {isContinuousMoving ? "Moving..." : "Move"}
                </Button>
                <Button
                  variant="contained"
                  color="error"
                  fullWidth
                  startIcon={
                    isContinuousStopping ? (
                      <CircularProgress enableTrackSlot size={16} />
                    ) : (
                      <ErrorOutline size={16} />
                    )
                  }
                  onClick={handleContinuousStop}
                  disabled={!isContinuousMoving || isContinuousStopping}
                >
                  Stop
                </Button>
              </Box>
            </Box>
          )}

          {/* Relative Movement */}
          {(relativePanTilt || relativeZoomSpace) && (
            <Box
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
              <Box display="flex" alignItems="center" gap={1}>
                <Tooltip
                  title="Move relative to current position. Translation is the offset, Speed controls the speed of movement."
                  arrow
                  placement="top"
                >
                  <Information size={16} />
                </Tooltip>
                <Typography variant="subtitle2">Relative Move</Typography>
              </Box>
              {relativePanTilt && (
                <>
                  {renderSlider(
                    relativePan,
                    relativePanTilt.XRange?.Min ?? -1,
                    relativePanTilt.XRange?.Max ?? 1,
                    "Pan Translation",
                    setRelativePan,
                  )}
                  {renderSlider(
                    relativeTilt,
                    relativePanTilt.YRange?.Min ?? -1,
                    relativePanTilt.YRange?.Max ?? 1,
                    "Tilt Translation",
                    setRelativeTilt,
                  )}
                  {panTiltSpeed && (
                    <>
                      {renderSlider(
                        relativePanSpeed ??
                          (panTiltSpeed.XRange?.Min ?? 0) +
                            (panTiltSpeed.XRange?.Max ?? 1) / 2,
                        panTiltSpeed.XRange?.Min ?? 0,
                        panTiltSpeed.XRange?.Max ?? 1,
                        "Pan Speed",
                        setRelativePanSpeed,
                      )}
                      {renderSlider(
                        relativeTiltSpeed ??
                          (panTiltSpeed.YRange?.Min ?? 0) +
                            (panTiltSpeed.YRange?.Max ?? 1) / 2,
                        panTiltSpeed.YRange?.Min ?? 0,
                        panTiltSpeed.YRange?.Max ?? 1,
                        "Tilt Speed",
                        setRelativeTiltSpeed,
                      )}
                    </>
                  )}
                </>
              )}
              {relativeZoomSpace && (
                <>
                  {renderSlider(
                    relativeZoom,
                    relativeZoomSpace.XRange?.Min ?? -1,
                    relativeZoomSpace.XRange?.Max ?? 1,
                    "Zoom Translation",
                    setRelativeZoom,
                  )}
                  {zoomSpeed &&
                    renderSlider(
                      relativeZoomSpeed ??
                        (zoomSpeed.XRange?.Min ?? 0) +
                          (zoomSpeed.XRange?.Max ?? 1) / 2,
                      zoomSpeed.XRange?.Min ?? 0,
                      zoomSpeed.XRange?.Max ?? 1,
                      "Zoom Speed",
                      setRelativeZoomSpeed,
                    )}
                </>
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
                    isRelativeMoving ? (
                      <GrowingSpinner color="primary.main" size={16} />
                    ) : (
                      <Move size={16} />
                    )
                  }
                  onClick={handleRelativeMove}
                  disabled={
                    isRelativeMoving ||
                    isContinuousMoving ||
                    isAbsoluteMoving ||
                    (relativePan === 0 &&
                      relativeTilt === 0 &&
                      relativeZoom === 0)
                  }
                >
                  {isRelativeMoving ? "Moving..." : "Move"}
                </Button>
                <Button
                  variant="contained"
                  color="error"
                  fullWidth
                  startIcon={
                    isRelativeStopping ? (
                      <CircularProgress enableTrackSlot size={16} />
                    ) : (
                      <ErrorOutline size={16} />
                    )
                  }
                  onClick={handleRelativeStop}
                  disabled={!isRelativeMoving || isRelativeStopping}
                >
                  Stop
                </Button>
              </Box>
            </Box>
          )}

          {/* Absolute Movement */}
          {(absolutePanTilt || absoluteZoomSpace) && (
            <Box
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
              <Box display="flex" alignItems="center" gap={1}>
                <Tooltip
                  title="Move to absolute position. Position is the target, Speed controls the speed of movement."
                  arrow
                  placement="top"
                >
                  <Information size={16} />
                </Tooltip>
                <Typography variant="subtitle2">Absolute Move</Typography>
              </Box>
              {absolutePanTilt && (
                <>
                  {renderSlider(
                    absolutePan,
                    absolutePanTilt.XRange?.Min ?? -1,
                    absolutePanTilt.XRange?.Max ?? 1,
                    "Pan Position",
                    setAbsolutePan,
                  )}
                  {renderSlider(
                    absoluteTilt,
                    absolutePanTilt.YRange?.Min ?? -1,
                    absolutePanTilt.YRange?.Max ?? 1,
                    "Tilt Position",
                    setAbsoluteTilt,
                  )}
                  {panTiltSpeed && (
                    <>
                      {renderSlider(
                        absolutePanSpeed ??
                          (panTiltSpeed.XRange?.Min ?? 0) +
                            (panTiltSpeed.XRange?.Max ?? 1) / 2,
                        panTiltSpeed.XRange?.Min ?? 0,
                        panTiltSpeed.XRange?.Max ?? 1,
                        "Pan Speed",
                        setAbsolutePanSpeed,
                      )}
                      {renderSlider(
                        absoluteTiltSpeed ??
                          (panTiltSpeed.YRange?.Min ?? 0) +
                            (panTiltSpeed.YRange?.Max ?? 1) / 2,
                        panTiltSpeed.YRange?.Min ?? 0,
                        panTiltSpeed.YRange?.Max ?? 1,
                        "Tilt Speed",
                        setAbsoluteTiltSpeed,
                      )}
                    </>
                  )}
                </>
              )}
              {absoluteZoomSpace && (
                <>
                  {renderSlider(
                    absoluteZoom,
                    absoluteZoomSpace.XRange?.Min ?? 0,
                    absoluteZoomSpace.XRange?.Max ?? 1,
                    "Zoom Position",
                    setAbsoluteZoom,
                  )}
                  {zoomSpeed &&
                    renderSlider(
                      absoluteZoomSpeed ??
                        (zoomSpeed.XRange?.Min ?? 0) +
                          (zoomSpeed.XRange?.Max ?? 1) / 2,
                      zoomSpeed.XRange?.Min ?? 0,
                      zoomSpeed.XRange?.Max ?? 1,
                      "Zoom Speed",
                      setAbsoluteZoomSpeed,
                    )}
                </>
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
                    isAbsoluteMoving ? (
                      <GrowingSpinner color="primary.main" size={16} />
                    ) : (
                      <Move size={16} />
                    )
                  }
                  onClick={handleAbsoluteMove}
                  disabled={
                    isAbsoluteMoving || isContinuousMoving || isRelativeMoving
                  }
                >
                  {isAbsoluteMoving ? "Moving..." : "Move"}
                </Button>
                <Button
                  variant="contained"
                  color="error"
                  fullWidth
                  startIcon={
                    isAbsoluteStopping ? (
                      <CircularProgress enableTrackSlot size={16} />
                    ) : (
                      <ErrorOutline size={16} />
                    )
                  }
                  onClick={handleAbsoluteStop}
                  disabled={!isAbsoluteMoving || isAbsoluteStopping}
                >
                  Stop
                </Button>
              </Box>
            </Box>
          )}
        </Box>
      </Box>
    </QueryWrapper>
  );
}
