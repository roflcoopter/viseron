import { useRef } from "react";

import { useToast } from "hooks/UseToast";
import {
  usePtzAbsoluteMove,
  usePtzContinuousMove,
  usePtzGoHome,
  usePtzGotoPreset,
  usePtzRemovePreset,
  usePtzSetHome,
  usePtzSetPreset,
  usePtzStop,
} from "lib/api/actions/onvif/ptz";

interface PtzMinMaxRanges {
  panTiltMinMax: {
    xMin: number;
    xMax: number;
    yMin: number;
    yMax: number;
  };
  zoomMinMax: {
    min: number;
    max: number;
  };
  speedMinMax: {
    panTiltMin: number;
    panTiltMax: number;
    zoomMin: number;
    zoomMax: number;
  };
}

interface UseOnvifPtzHandlersParams {
  cameraIdentifier: string;
  isAutoConfig: boolean;
  moveSpeed: number;
  reversePan: boolean;
  reverseTilt: boolean;
  ranges: PtzMinMaxRanges;
  refetchPresets: () => void;
  setPresetsDialogOpen: (open: boolean) => void;
  setSetHomeDialogOpen: (open: boolean) => void;
  setNewPresetName: (name: string) => void;
  setSavePresetDialogOpen: (open: boolean) => void;
  presetsData?: any;
  configData?: any;
}

export function useOnvifPtzHandlers({
  cameraIdentifier,
  isAutoConfig,
  moveSpeed,
  reversePan,
  reverseTilt,
  ranges,
  refetchPresets,
  setPresetsDialogOpen,
  setSetHomeDialogOpen,
  setNewPresetName,
  setSavePresetDialogOpen,
  configData,
}: UseOnvifPtzHandlersParams) {
  const toast = useToast();

  const isMoveActiveRef = useRef(false);
  const moveParamsRef = useRef<{
    xVelocity: number;
    yVelocity: number;
    zoomVelocity: number;
  }>({ xVelocity: 0, yVelocity: 0, zoomVelocity: 0 });

  const continuousMoveMutation = usePtzContinuousMove();
  const absoluteMoveMutation = usePtzAbsoluteMove();
  const stopMutation = usePtzStop();
  const goHomeMutation = usePtzGoHome();
  const gotoPresetMutation = usePtzGotoPreset();
  const setHomeMutation = usePtzSetHome();
  const setPresetMutation = usePtzSetPreset();
  const removePresetMutation = usePtzRemovePreset();

  // Helper function to clamp velocity values to camera's supported range
  const clampVelocity = (
    x: number,
    y: number,
    zoom: number,
  ): { x: number; y: number; zoom: number } => ({
    x: Math.max(
      ranges.panTiltMinMax.xMin,
      Math.min(ranges.panTiltMinMax.xMax, x),
    ),
    y: Math.max(
      ranges.panTiltMinMax.yMin,
      Math.min(ranges.panTiltMinMax.yMax, y),
    ),
    zoom: Math.max(
      ranges.zoomMinMax.min,
      Math.min(ranges.zoomMinMax.max, zoom),
    ),
  });

  const stopContinuousMove = () => {
    isMoveActiveRef.current = false;
    stopMutation.mutate(
      { cameraIdentifier },
      {
        onError: (error) => {
          toast.error(error.message || "Failed to stop camera movement");
        },
      },
    );
  };

  const startContinuousMove = (
    xVelocity: number,
    yVelocity: number,
    zoomVelocity: number = 0,
  ) => {
    // Prevent multiple intervals
    if (isMoveActiveRef.current) return;

    isMoveActiveRef.current = true;
    moveParamsRef.current = { xVelocity, yVelocity, zoomVelocity };

    // Function to send move command
    const sendMoveCommand = () => {
      const velocities = clampVelocity(
        moveParamsRef.current.xVelocity * moveSpeed,
        moveParamsRef.current.yVelocity * moveSpeed,
        moveParamsRef.current.zoomVelocity * moveSpeed,
      );
      continuousMoveMutation.mutate(
        {
          cameraIdentifier,
          params: {
            x_velocity: velocities.x,
            y_velocity: velocities.y,
            zoom_velocity: velocities.zoom,
          },
        },
        {
          onError: (error) => {
            stopContinuousMove();
            toast.error(error.message || "Failed to move camera");
          },
        },
      );
    };

    // Send first command immediately
    sendMoveCommand();
  };

  const handleMoveStart = (
    xVelocity: number,
    yVelocity: number,
    zoomVelocity: number = 0,
  ) => {
    // Helper to reverse only if value is not zero
    const reverseIfNeeded = (value: number, reverse: boolean) =>
      value === 0 ? 0 : reverse ? -value : value;

    let adjustedX: number;
    let adjustedY: number;

    if (isAutoConfig) {
      // Autoconfig true, use UI toggles directly
      adjustedX = reverseIfNeeded(xVelocity, reversePan);
      adjustedY = reverseIfNeeded(yVelocity, reverseTilt);
    } else {
      const isReversePan = configData?.user_config?.reverse_pan;
      const isReverseTilt = configData?.user_config?.reverse_tilt;
      // Autoconfig false, use camera config toggles inverted
      adjustedX = reverseIfNeeded(
        xVelocity,
        !isReversePan ? reversePan : !reversePan,
      );
      adjustedY = reverseIfNeeded(
        yVelocity,
        !isReverseTilt ? reverseTilt : !reverseTilt,
      );
    }

    startContinuousMove(adjustedX, adjustedY, zoomVelocity);
  };

  const handleStop = () => {
    stopContinuousMove();
  };

  const handleGoHome = () => {
    goHomeMutation.mutate(
      { cameraIdentifier },
      {
        onError: (error) => {
          toast.error(error.message || "Failed to go to home position");
        },
      },
    );
  };

  const handleSetHome = () => {
    setHomeMutation.mutate(
      { cameraIdentifier },
      {
        onSuccess: () => {
          setSetHomeDialogOpen(false);
          toast.success("Home position set successfully");
        },
        onError: (error) => {
          toast.error(error.message || "Failed to set home position");
        },
      },
    );
  };

  const handleGotoPreset = (presetToken: string) => {
    gotoPresetMutation.mutate(
      {
        cameraIdentifier,
        presetToken,
      },
      {
        onError: (error) => {
          toast.error(error.message || "Failed to go to preset");
        },
      },
    );
    setPresetsDialogOpen(false);
  };

  const handleAbsoluteMove = (
    x_position: number,
    y_position: number,
    zoom_position?: number,
    is_adjusted?: boolean,
  ) => {
    absoluteMoveMutation.mutate(
      {
        cameraIdentifier,
        params: {
          x_position,
          y_position,
          zoom_position,
          is_adjusted,
        },
      },
      {
        onError: (error) => {
          toast.error(error.message || "Failed to move camera");
        },
      },
    );
    setPresetsDialogOpen(false);
  };

  const handleSavePreset = (presetName: string) => {
    if (presetName.trim()) {
      setPresetMutation.mutate(
        {
          cameraIdentifier,
          presetName: presetName.trim(),
        },
        {
          onSuccess: () => {
            refetchPresets();
            setNewPresetName("");
            setSavePresetDialogOpen(false);
            toast.success(`Preset "${presetName.trim()}" saved successfully`);
          },
          onError: (error) => {
            toast.error(error.message || "Failed to save preset");
          },
        },
      );
    }
  };

  const handleRemovePreset = (presetToken: string) => {
    removePresetMutation.mutate(
      {
        cameraIdentifier,
        presetToken,
      },
      {
        onSuccess: () => {
          refetchPresets();
          toast.success("Preset removed successfully");
        },
        onError: (error) => {
          toast.error(error.message || "Failed to remove preset");
        },
      },
    );
  };

  return {
    handleMoveStart,
    handleStop,
    handleGoHome,
    handleSetHome,
    handleGotoPreset,
    handleSavePreset,
    handleRemovePreset,
    handleAbsoluteMove,
    mutations: {
      setHomeMutation,
      setPresetMutation,
      removePresetMutation,
    },
  };
}
