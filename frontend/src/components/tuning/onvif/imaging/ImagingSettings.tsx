import {
  Aperture,
  AudioConsole,
  BrightnessContrast,
  ColorSwitch,
  Contrast,
  CutOut,
  Flash,
  Fog,
  Gradient,
  Help,
  Image,
  ImageReference,
  Incomplete,
  Opacity,
  UvIndex,
} from "@carbon/icons-react";
import {
  Box,
  Button,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Slider,
  Tooltip,
  Typography,
} from "@mui/material";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useToast } from "hooks/UseToast";
import {
  useGetImagingOptions,
  useGetImagingSettings,
  useSetImagingSettings,
} from "lib/api/actions/onvif/imaging";

import { QueryWrapper } from "../../config/QueryWrapper";

// Utility: Deep merge two objects recursively
const deepMerge = (base: any, overrides: any): any => {
  if (!overrides) return base;
  if (!base) return overrides;
  if (typeof base !== "object" || typeof overrides !== "object")
    return overrides;
  if (Array.isArray(base) || Array.isArray(overrides)) return overrides;

  const result = { ...base };
  for (const key of Object.keys(overrides)) {
    if (overrides[key] !== undefined) {
      result[key] = deepMerge(base[key], overrides[key]);
    }
  }
  return result;
};

// Utility: Parse ISO 8601 duration (PT3S, PT120S) to seconds
const parsePTDuration = (pt: string | undefined): number | undefined => {
  if (!pt) return undefined;
  const match = pt.match(/PT(\d+)S/);
  return match ? parseInt(match[1], 10) : undefined;
};

// Utility: Format seconds to ISO 8601 duration (PT3S)
const formatPTDuration = (seconds: number): string => `PT${seconds}S`;

const ImagingUpdates = {
  // Top level settings
  brightness: (v: number) => ({ Brightness: v }),
  colorSaturation: (v: number) => ({ ColorSaturation: v }),
  contrast: (v: number) => ({ Contrast: v }),
  sharpness: (v: number) => ({ Sharpness: v }),
  irCutFilter: (v: string) => ({ IrCutFilter: v }),

  // White Balance
  whiteBalanceMode: (v: string) => ({ WhiteBalance: { Mode: v } }),
  whiteBalanceCrGain: (v: number) => ({ WhiteBalance: { CrGain: v } }),
  whiteBalanceCbGain: (v: number) => ({ WhiteBalance: { CbGain: v } }),

  // Backlight Compensation
  backlightMode: (v: string) => ({ BacklightCompensation: { Mode: v } }),
  backlightLevel: (v: number) => ({ BacklightCompensation: { Level: v } }),

  // Wide Dynamic Range
  wdrMode: (v: string) => ({ WideDynamicRange: { Mode: v } }),
  wdrLevel: (v: number) => ({ WideDynamicRange: { Level: v } }),

  // Exposure
  exposureMode: (v: string) => ({ Exposure: { Mode: v } }),
  exposurePriority: (v: string) => ({ Exposure: { Priority: v } }),
  exposureMinGain: (v: number) => ({ Exposure: { MinGain: v } }),
  exposureMaxGain: (v: number) => ({ Exposure: { MaxGain: v } }),
  exposureMinTime: (v: number) => ({ Exposure: { MinExposureTime: v } }),
  exposureMaxTime: (v: number) => ({ Exposure: { MaxExposureTime: v } }),
  exposureMinIris: (v: number) => ({ Exposure: { MinIris: v } }),
  exposureMaxIris: (v: number) => ({ Exposure: { MaxIris: v } }),
  exposureGain: (v: number) => ({ Exposure: { Gain: v } }),
  exposureTime: (v: number) => ({ Exposure: { ExposureTime: v } }),
  exposureIris: (v: number) => ({ Exposure: { Iris: v } }),

  // Focus
  focusMode: (v: string) => ({ Focus: { AutoFocusMode: v } }),

  // Extension - Image Stabilization (1 level extension)
  imageStabilizationMode: (v: string) => ({
    Extension: { ImageStabilization: { Mode: v } },
  }),
  imageStabilizationLevel: (v: number) => ({
    Extension: { ImageStabilization: { Level: v } },
  }),

  // Extension - IrCutFilterAutoAdjustment (2 level extension)
  irCutFilterAutoAdjustmentBoundaryType: (v: string) => ({
    Extension: {
      Extension: { IrCutFilterAutoAdjustment: { BoundaryType: v } },
    },
  }),
  irCutFilterAutoAdjustmentBoundaryOffset: (v: number) => ({
    Extension: {
      Extension: { IrCutFilterAutoAdjustment: { BoundaryOffset: v } },
    },
  }),
  irCutFilterAutoAdjustmentResponseTime: (v: string) => ({
    Extension: {
      Extension: { IrCutFilterAutoAdjustment: { ResponseTime: v } },
    },
  }),

  // Extension - Tone Compensation (3 level extension)
  toneCompensationMode: (v: string) => ({
    Extension: { Extension: { Extension: { ToneCompensation: { Mode: v } } } },
  }),
  toneCompensationLevel: (v: number) => ({
    Extension: { Extension: { Extension: { ToneCompensation: { Level: v } } } },
  }),

  // Extension - Defogging (3 level extension)
  defoggingMode: (v: string) => ({
    Extension: { Extension: { Extension: { Defogging: { Mode: v } } } },
  }),
  defoggingLevel: (v: number) => ({
    Extension: { Extension: { Extension: { Defogging: { Level: v } } } },
  }),

  // Extension - Noise Reduction (3 level extension)
  noiseReductionLevel: (v: number) => ({
    Extension: { Extension: { Extension: { NoiseReduction: { Level: v } } } },
  }),
};

interface ImagingSettingsProps {
  cameraIdentifier: string;
  onSettingsApplied?: () => void;
}

export function ImagingSettings({
  cameraIdentifier,
  onSettingsApplied,
}: ImagingSettingsProps) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const {
    data: imagingSettings,
    isLoading,
    isError,
    error,
  } = useGetImagingSettings(cameraIdentifier);
  const { data: imagingOptions } = useGetImagingOptions(cameraIdentifier);
  const setImagingSettingsMutation = useSetImagingSettings(cameraIdentifier);

  const [localSettings, setLocalSettings] = useState<any>({});
  const [isApplying, setIsApplying] = useState(false);

  // Custom options from ONVIF WSDL SCHEMA, don't delete it!
  const TONE_COMPENSATION_MODES = ["OFF", "ON"]; // "AUTO"
  const DEFOGGING_MODES = ["OFF", "ON"]; // "AUTO"
  const IRCUT_FILTER_BOUNDARY_TYPES = ["Common", "ToOn", "ToOff", "Extended"];

  // Deep merge settings to preserve nested object values
  const settings = deepMerge(imagingSettings?.settings, localSettings);
  const options = imagingOptions?.options;

  const handleValueChange = (update: any) => {
    setLocalSettings((prev: any) => deepMerge(prev, update));
  };

  const handleApplySettings = async () => {
    if (Object.keys(localSettings).length === 0) {
      return;
    }

    // Clone localSettings for modification
    const settingsToSend = JSON.parse(JSON.stringify(localSettings));

    // Helper: include Mode from settings if not present in settingsToSend
    const includeMode = (
      getTarget: (obj: any) => any,
      getSource: (obj: any) => any,
    ) => {
      const target = getTarget(settingsToSend);
      if (target && !target.Mode) {
        target.Mode = getSource(settings)?.Mode;
      }
    };

    includeMode(
      (o) => o.WhiteBalance,
      (s) => s?.WhiteBalance,
    );
    includeMode(
      (o) => o.BacklightCompensation,
      (s) => s?.BacklightCompensation,
    );
    includeMode(
      (o) => o.WideDynamicRange,
      (s) => s?.WideDynamicRange,
    );
    includeMode(
      (o) => o.Exposure,
      (s) => s?.Exposure,
    );
    includeMode(
      (o) => o.Extension?.ImageStabilization,
      (s) => s?.Extension?.ImageStabilization,
    );
    includeMode(
      (o) => o.Extension?.Extension?.Extension?.ToneCompensation,
      (s) => s?.Extension?.Extension?.Extension?.ToneCompensation,
    );
    includeMode(
      (o) => o.Extension?.Extension?.Extension?.Defogging,
      (s) => s?.Extension?.Extension?.Extension?.Defogging,
    );

    // IrCutFilterAutoAdjustment: include BoundaryType if not present
    const irCutFilterAutoAdjustment =
      settingsToSend.Extension?.Extension?.IrCutFilterAutoAdjustment;
    if (irCutFilterAutoAdjustment && !irCutFilterAutoAdjustment.BoundaryType) {
      irCutFilterAutoAdjustment.BoundaryType =
        settings?.Extension?.Extension?.IrCutFilterAutoAdjustment?.BoundaryType;
    }

    setIsApplying(true);
    setImagingSettingsMutation.mutate(
      {
        settings: settingsToSend,
        forcePersistence: false,
      },
      {
        onSuccess: async () => {
          toast.success("Imaging settings applied successfully");
          await queryClient.invalidateQueries({
            queryKey: ["imaging", "settings", cameraIdentifier],
          });
          setLocalSettings({});
          setIsApplying(false);
          // Trigger snapshot refresh after successful settings application with delay
          setTimeout(() => onSettingsApplied?.(), 2000);
        },
        onError: (err) => {
          toast.error(err?.message || "Failed to apply imaging settings");
          setIsApplying(false);
        },
      },
    );
  };

  const renderSlider = (
    label: string,
    icon: React.ReactNode,
    value: number,
    min: number,
    max: number,
    onChange: (value: number) => void,
    step: number = 1,
  ) => {
    if (
      typeof value !== "number" ||
      typeof min !== "number" ||
      typeof max !== "number"
    ) {
      return null;
    }
    const thumbWidth = 16;
    const halfThumb = thumbWidth / 2;

    return (
      <FormControl fullWidth>
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 0.5,
          }}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
            {icon}
            <Typography variant="caption">{label}</Typography>
          </Box>
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
  };

  const renderSelect = (
    label: string,
    value: string | undefined,
    selectOptions: string[] | undefined,
    onChange?: (value: string) => void,
  ) => {
    if (!selectOptions || selectOptions.length === 0) {
      return null;
    }

    return (
      <FormControl fullWidth sx={{ mt: 1, mb: 1 }}>
        <InputLabel>{label}</InputLabel>
        <Select
          value={value || selectOptions[0]}
          label={label}
          size="medium"
          variant="filled"
          onChange={(e) => onChange?.(e.target.value)}
        >
          {selectOptions.map((option) => (
            <MenuItem key={option} value={option}>
              {option}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    );
  };

  return (
    <QueryWrapper
      isLoading={isLoading}
      isError={isError}
      errorMessage={error?.message || "Failed to load imaging settings"}
      isEmpty={!imagingSettings}
      emptyMessage="No imaging settings available"
      title="Imaging Settings"
    >
      <Box>
        <Box
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          mb={1.5}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Typography variant="subtitle2">Imaging Settings</Typography>
            <Tooltip
              title="Manage ONVIF imaging settings for the camera. Some cameras may ignore the parameters defined here."
              arrow
              placement="top"
            >
              <Help size={16} />
            </Tooltip>
          </Box>
        </Box>
        <Box display="flex" flexDirection="column" gap={1}>
          {/* Brightness */}
          {renderSlider(
            "Brightness",
            <BrightnessContrast size={16} />,
            settings?.Brightness,
            options?.Brightness?.Min,
            options?.Brightness?.Max,
            (value) => handleValueChange(ImagingUpdates.brightness(value)),
            0.01,
          )}
          {/* Color Saturation */}
          {renderSlider(
            "Color Saturation",
            <ColorSwitch size={16} />,
            settings?.ColorSaturation,
            options?.ColorSaturation?.Min,
            options?.ColorSaturation?.Max,
            (value) => handleValueChange(ImagingUpdates.colorSaturation(value)),
            0.01,
          )}
          {/* Contrast */}
          {renderSlider(
            "Contrast",
            <Contrast size={16} />,
            settings?.Contrast,
            options?.Contrast?.Min,
            options?.Contrast?.Max,
            (value) => handleValueChange(ImagingUpdates.contrast(value)),
            0.01,
          )}
          {/* Sharpness */}
          {renderSlider(
            "Sharpness",
            <Gradient size={16} />,
            settings?.Sharpness,
            options?.Sharpness?.Min,
            options?.Sharpness?.Max,
            (value) => handleValueChange(ImagingUpdates.sharpness(value)),
            0.01,
          )}
          {/* Ircut Filter Mode */}
          {renderSelect(
            "Infrared Cutoff Filter",
            settings?.IrCutFilter,
            options?.IrCutFilterModes,
            (value) => handleValueChange(ImagingUpdates.irCutFilter(value)),
          )}
          {/* IrCutFilterAutoAdjustment Boundary Type */}
          {settings?.IrCutFilter === "AUTO" &&
            options?.Extension?.Extension?.IrCutFilterAutoAdjustment
              ?.BoundaryType &&
            renderSelect(
              "IrCutFilter Auto Adjustment Boundary",
              settings?.Extension?.Extension?.IrCutFilterAutoAdjustment
                ?.BoundaryType,
              IRCUT_FILTER_BOUNDARY_TYPES,
              (value) =>
                handleValueChange(
                  ImagingUpdates.irCutFilterAutoAdjustmentBoundaryType(value),
                ),
            )}
          {/* IrCutFilterAutoAdjustment Boundary Offset */}
          {settings?.IrCutFilter === "AUTO" &&
            options?.Extension?.Extension?.IrCutFilterAutoAdjustment
              ?.BoundaryOffset &&
            renderSlider(
              "IrCutFilter Auto Adjustment Boundary Offset",
              <Flash size={16} />,
              settings?.Extension?.Extension?.IrCutFilterAutoAdjustment
                ?.BoundaryOffset,
              -1.0,
              1.0,
              (value) =>
                handleValueChange(
                  ImagingUpdates.irCutFilterAutoAdjustmentBoundaryOffset(value),
                ),
              0.1,
            )}
          {/* IrCutFilterAutoAdjustment Response Time */}
          {settings?.IrCutFilter === "AUTO" &&
            options?.Extension?.Extension?.IrCutFilterAutoAdjustment
              ?.ResponseTimeRange &&
            renderSlider(
              "IrCutFilter Auto Adjustment Response Time (s)",
              <Flash size={16} />,
              parsePTDuration(
                settings?.Extension?.Extension?.IrCutFilterAutoAdjustment
                  ?.ResponseTime,
              ) ?? 3,
              parsePTDuration(
                options?.Extension?.Extension?.IrCutFilterAutoAdjustment
                  ?.ResponseTimeRange?.Min,
              ) ?? 3,
              parsePTDuration(
                options?.Extension?.Extension?.IrCutFilterAutoAdjustment
                  ?.ResponseTimeRange?.Max,
              ) ?? 120,
              (value) =>
                handleValueChange(
                  ImagingUpdates.irCutFilterAutoAdjustmentResponseTime(
                    formatPTDuration(value),
                  ),
                ),
              1,
            )}
          {/* White Balance Mode */}
          {renderSelect(
            "White Balance",
            settings?.WhiteBalance?.Mode,
            options?.WhiteBalance?.Mode,
            (value) =>
              handleValueChange(ImagingUpdates.whiteBalanceMode(value)),
          )}
          {/* White Balance Level */}
          {settings?.WhiteBalance?.Mode === "MANUAL" &&
            renderSlider(
              "White Balance CrGain",
              <Incomplete size={16} />,
              settings?.WhiteBalance?.CrGain,
              options?.WhiteBalance?.YrGain?.Min,
              options?.WhiteBalance?.YrGain?.Max,
              (value) =>
                handleValueChange(ImagingUpdates.whiteBalanceCrGain(value)),
              0.5,
            )}
          {settings?.WhiteBalance?.Mode === "MANUAL" &&
            renderSlider(
              "White Balance CbGain",
              <Incomplete size={16} />,
              settings?.WhiteBalance?.CbGain,
              options?.WhiteBalance?.YbGain?.Min,
              options?.WhiteBalance?.YbGain?.Max,
              (value) =>
                handleValueChange(ImagingUpdates.whiteBalanceCbGain(value)),
              0.5,
            )}
          {/* Backlight Compensation Mode */}
          {renderSelect(
            "Backlight Compensation",
            settings?.BacklightCompensation?.Mode,
            options?.BacklightCompensation?.Mode,
            (value) => handleValueChange(ImagingUpdates.backlightMode(value)),
          )}
          {/* Backlight Compensation Level */}
          {settings?.BacklightCompensation?.Mode === "ON" &&
            renderSlider(
              "Backlight Compensation Level",
              <Aperture size={16} />,
              settings?.BacklightCompensation?.Level,
              options?.BacklightCompensation?.Level?.Min,
              options?.BacklightCompensation?.Level?.Max,
              (value) =>
                handleValueChange(ImagingUpdates.backlightLevel(value)),
              1,
            )}
          {/* Wide Dynamic Range Mode */}
          {renderSelect(
            "Wide Dynamic Range",
            settings?.WideDynamicRange?.Mode,
            options?.WideDynamicRange?.Mode,
            (value) => handleValueChange(ImagingUpdates.wdrMode(value)),
          )}
          {/* Wide Dynamic Range Level */}
          {settings?.WideDynamicRange?.Mode === "ON" &&
            renderSlider(
              "Wide Dynamic Range Level",
              <Opacity size={16} />,
              settings?.WideDynamicRange?.Level,
              options?.WideDynamicRange?.Level?.Min,
              options?.WideDynamicRange?.Level?.Max,
              (value) => handleValueChange(ImagingUpdates.wdrLevel(value)),
              1,
            )}
          {/* Exposure Mode */}
          {renderSelect(
            "Exposure",
            settings?.Exposure?.Mode,
            options?.Exposure?.Mode,
            (value) => handleValueChange(ImagingUpdates.exposureMode(value)),
          )}
          {/* Exposure Priority */}
          {renderSelect(
            "Exposure Priority",
            settings?.Exposure?.Priority,
            options?.Exposure?.Priority,
            (value) =>
              handleValueChange(ImagingUpdates.exposurePriority(value)),
          )}
          {/* Exposure Min Gain */}
          {settings?.Exposure?.Mode === "AUTO" &&
            renderSlider(
              "Exposure Min Gain",
              <UvIndex size={16} />,
              settings?.Exposure?.MinGain,
              options?.Exposure?.MinGain?.Min,
              options?.Exposure?.MinGain?.Max,
              (value) =>
                handleValueChange(ImagingUpdates.exposureMinGain(value)),
              0.5,
            )}
          {/* Exposure Max Gain */}
          {settings?.Exposure?.Mode === "AUTO" &&
            renderSlider(
              "Exposure Max Gain",
              <UvIndex size={16} />,
              settings?.Exposure?.MaxGain,
              options?.Exposure?.MaxGain?.Min,
              options?.Exposure?.MaxGain?.Max,
              (value) =>
                handleValueChange(ImagingUpdates.exposureMaxGain(value)),
              0.5,
            )}
          {/* Exposure Min Time */}
          {settings?.Exposure?.Mode === "AUTO" &&
            renderSlider(
              "Exposure Min Time",
              <UvIndex size={16} />,
              settings?.Exposure?.MinExposureTime,
              options?.Exposure?.MinExposureTime?.Min,
              options?.Exposure?.MinExposureTime?.Max,
              (value) =>
                handleValueChange(ImagingUpdates.exposureMinTime(value)),
              0.5,
            )}
          {/* Exposure Max Time */}
          {settings?.Exposure?.Mode === "AUTO" &&
            renderSlider(
              "Exposure Max Time",
              <UvIndex size={16} />,
              settings?.Exposure?.MaxExposureTime,
              options?.Exposure?.MaxExposureTime?.Min,
              options?.Exposure?.MaxExposureTime?.Max,
              (value) =>
                handleValueChange(ImagingUpdates.exposureMaxTime(value)),
              0.5,
            )}
          {/* Exposure Min Iris */}
          {settings?.Exposure?.Mode === "AUTO" &&
            renderSlider(
              "Exposure Min Iris",
              <UvIndex size={16} />,
              settings?.Exposure?.MinIris,
              options?.Exposure?.MinIris?.Min,
              options?.Exposure?.MinIris?.Max,
              (value) =>
                handleValueChange(ImagingUpdates.exposureMinIris(value)),
              0.5,
            )}
          {/* Exposure Max Iris */}
          {settings?.Exposure?.Mode === "AUTO" &&
            renderSlider(
              "Exposure Max Iris",
              <UvIndex size={16} />,
              settings?.Exposure?.MaxIris,
              options?.Exposure?.MaxIris?.Min,
              options?.Exposure?.MaxIris?.Max,
              (value) =>
                handleValueChange(ImagingUpdates.exposureMaxIris(value)),
              0.5,
            )}
          {/* Exposure Gain */}
          {settings?.Exposure?.Mode === "MANUAL" &&
            renderSlider(
              "Exposure Gain",
              <UvIndex size={16} />,
              settings?.Exposure?.Gain,
              options?.Exposure?.Gain?.Min,
              options?.Exposure?.Gain?.Max,
              (value) => handleValueChange(ImagingUpdates.exposureGain(value)),
              0.5,
            )}
          {/* Exposure Time */}
          {settings?.Exposure?.Mode === "MANUAL" &&
            renderSlider(
              "Exposure Time",
              <UvIndex size={16} />,
              settings?.Exposure?.ExposureTime,
              options?.Exposure?.ExposureTime?.Min,
              options?.Exposure?.ExposureTime?.Max,
              (value) => handleValueChange(ImagingUpdates.exposureTime(value)),
              0.5,
            )}
          {/* Exposure Iris */}
          {settings?.Exposure?.Mode === "MANUAL" &&
            renderSlider(
              "Exposure Iris",
              <UvIndex size={16} />,
              settings?.Exposure?.Iris,
              options?.Exposure?.Iris?.Min,
              options?.Exposure?.Iris?.Max,
              (value) => handleValueChange(ImagingUpdates.exposureIris(value)),
              0.5,
            )}
          {/* Auto Focus Mode */}
          {renderSelect(
            "Auto Focus",
            settings?.Focus?.AutoFocusMode,
            options?.Focus?.AutoFocusModes,
            (value) => handleValueChange(ImagingUpdates.focusMode(value)),
          )}
          {/* Image Stabilization Mode */}
          {renderSelect(
            "Image Stabilization",
            settings?.Extension?.ImageStabilization?.Mode,
            options?.Extension?.ImageStabilization?.Mode,
            (value) =>
              handleValueChange(ImagingUpdates.imageStabilizationMode(value)),
          )}
          {/* Image Stabilization Level */}
          {renderSlider(
            "Image Stabilization Level",
            <Image size={16} />,
            settings?.Extension?.ImageStabilization?.Level,
            options?.Extension?.ImageStabilization?.Level?.Min,
            options?.Extension?.ImageStabilization?.Level?.Max,
            (value) =>
              handleValueChange(ImagingUpdates.imageStabilizationLevel(value)),
            0.5,
          )}
          {/* Tone Compensation Mode */}
          {options?.Extension?.Extension?.Extension?.ToneCompensationOptions
            ?.Mode &&
            renderSelect(
              "Tone Compensation",
              settings?.Extension?.Extension?.Extension?.ToneCompensation?.Mode,
              TONE_COMPENSATION_MODES,
              (value) =>
                handleValueChange(ImagingUpdates.toneCompensationMode(value)),
            )}
          {/* Tone Compensation Level */}
          {["ON", "AUTO"].includes(
            settings?.Extension?.Extension?.Extension?.ToneCompensation?.Mode,
          ) &&
            options?.Extension?.Extension?.Extension?.ToneCompensationOptions
              ?.Level &&
            renderSlider(
              "Tone Compensation Level",
              <AudioConsole size={16} />,
              settings?.Extension?.Extension?.Extension?.ToneCompensation
                ?.Level,
              0.0,
              1.0,
              (value) =>
                handleValueChange(ImagingUpdates.toneCompensationLevel(value)),
              0.125,
            )}
          {/* Defogging Mode */}
          {options?.Extension?.Extension?.Extension?.DefoggingOptions?.Mode &&
            renderSelect(
              "Defogging",
              settings?.Extension?.Extension?.Extension?.Defogging?.Mode,
              DEFOGGING_MODES,
              (value) => handleValueChange(ImagingUpdates.defoggingMode(value)),
            )}
          {/* Defogging Level */}
          {["ON", "AUTO"].includes(
            settings?.Extension?.Extension?.Extension?.Defogging?.Mode,
          ) &&
            options?.Extension?.Extension?.Extension?.DefoggingOptions?.Level &&
            renderSlider(
              "Defogging Level",
              <Fog size={16} />,
              settings?.Extension?.Extension?.Extension?.Defogging?.Level,
              0.0,
              1.0,
              (value) =>
                handleValueChange(ImagingUpdates.defoggingLevel(value)),
              0.125,
            )}
          {options?.Extension?.Extension?.Extension?.NoiseReductionOptions
            ?.Level &&
            renderSlider(
              "Noise Reduction Level",
              <CutOut size={16} />,
              settings?.Extension?.Extension?.Extension?.NoiseReduction?.Level,
              0.0,
              1.0,
              (value) =>
                handleValueChange(ImagingUpdates.noiseReductionLevel(value)),
              0.0001,
            )}
          {/* Apply Config */}
          <Box
            pt={2}
            sx={{
              borderTop: 1,
              borderColor: "divider",
            }}
          >
            <Button
              variant="contained"
              color="primary"
              fullWidth
              startIcon={
                isApplying ? (
                  <CircularProgress enableTrackSlot size={16} />
                ) : (
                  <ImageReference size={16} />
                )
              }
              onClick={handleApplySettings}
              disabled={isApplying || Object.keys(localSettings).length === 0}
            >
              {isApplying ? "Applying..." : "Apply Settings"}
            </Button>
          </Box>
        </Box>
      </Box>
    </QueryWrapper>
  );
}
