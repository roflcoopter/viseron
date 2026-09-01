import { GlobalFilters, Help } from "@carbon/icons-react";
import {
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  TextField,
  Tooltip,
  Typography,
  tableCellClasses,
} from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { useMemo, useState } from "react";

import { useToast } from "hooks/UseToast";
import { useFormChanges } from "hooks/useFormChanges";
import {
  useGetPtzConfigurationOptions,
  usePtzSetConfiguration,
} from "lib/api/actions/onvif/ptz";
import * as onvif_types from "lib/api/actions/onvif/types";
import * as types from "lib/types";

import { QueryWrapper } from "../../config/QueryWrapper";

// Helpers
const getSecondsFromDuration = (duration?: string): number | "" => {
  if (!duration) {
    return "";
  }
  const [hours, minutes, seconds] = duration.split(":").map(Number);

  return hours * 3600 + minutes * 60 + seconds;
};

export function getDurationFromSeconds(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) {
    throw new Error(`Invalid duration seconds: ${seconds}`);
  }

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = seconds % 60;

  return `PT${hours > 0 ? `${hours}H` : ""}${
    minutes > 0 ? `${minutes}M` : ""
  }${remainingSeconds > 0 ? `${remainingSeconds}S` : ""}`;
}

function getChangedConfiguration(
  original: any,
  current: any,
): Record<string, any> {
  const result: Record<string, any> = {
    Name: original.Name,
    UseCount: original.UseCount,
    NodeToken: original.NodeToken,
    token: original.token,
  };

  Object.keys(current).forEach((key) => {
    if (["Name", "UseCount", "NodeToken", "token"].includes(key)) {
      return;
    }

    if (JSON.stringify(current[key]) !== JSON.stringify(original[key])) {
      result[key] = current[key];
    }
  });

  return result;
}

interface PTZConfigurationProps {
  cameraIdentifier: string;
  ptzConfigurations?: onvif_types.PtzConfigurationsResponse;
  isLoading: boolean;
  isError: boolean;
  error: types.APIErrorResponse | null;
}

export function PTZConfiguration({
  cameraIdentifier,
  ptzConfigurations,
  isLoading,
  isError,
  error,
}: PTZConfigurationProps) {
  const TITLE = "PTZ Configuration";
  const DESC =
    "Manage PTZ configuration for the camera; all these configurations will affect PTZ behavior.";

  const theme = useTheme();
  const toast = useToast();

  // ONVIF API hooks
  const { data: ptzConfigurationOptions } =
    useGetPtzConfigurationOptions(cameraIdentifier);
  const setConfigurationMutation = usePtzSetConfiguration();

  // Use configurationOrigin from from first node
  const configurationOrigin = ptzConfigurations?.configurations[0];
  const configurationOptions = ptzConfigurationOptions?.configuration_options;
  const infoItems: { label: string; value: string }[] = [];

  // Data extraction for display
  if (configurationOrigin?.DefaultPTZSpeed?.PanTilt) {
    infoItems.push(
      {
        label: "Default Pan Speed (Absolute/Relative)",
        value: configurationOrigin.DefaultPTZSpeed.PanTilt.x,
      },
      {
        label: "Default Tilt Speed (Absolute/Relative)",
        value: configurationOrigin.DefaultPTZSpeed.PanTilt.y,
      },
    );
  }
  if (configurationOrigin?.DefaultPTZSpeed?.Zoom) {
    infoItems.push({
      label: "Default Zoom Speed (Absolute/Relative)",
      value: configurationOrigin.DefaultPTZSpeed.Zoom.x,
    });
  }
  if (configurationOrigin?.DefaultPTZTimeout) {
    infoItems.push({
      label: "Default PTZ Timeout (Continuous)",
      value: configurationOrigin.DefaultPTZTimeout,
    });
  }

  if (configurationOrigin?.PanTiltLimits?.Range?.XRange) {
    infoItems.push(
      {
        label: "Min. Pan Limit (Absolute)",
        value: configurationOrigin.PanTiltLimits.Range.XRange.Min,
      },
      {
        label: "Max. Pan Limit (Absolute)",
        value: configurationOrigin.PanTiltLimits.Range.XRange.Max,
      },
    );
  }
  if (configurationOrigin?.PanTiltLimits?.Range?.YRange) {
    infoItems.push(
      {
        label: "Min. Tilt Limit (Absolute)",
        value: configurationOrigin.PanTiltLimits.Range.YRange.Min,
      },
      {
        label: "Max. Tilt Limit (Absolute)",
        value: configurationOrigin.PanTiltLimits.Range.YRange.Max,
      },
    );
  }
  if (configurationOrigin?.ZoomLimits?.Range?.XRange) {
    infoItems.push(
      {
        label: "Min. Zoom Limit (Absolute)",
        value: configurationOrigin.ZoomLimits.Range.XRange.Min,
      },
      {
        label: "Max. Zoom Limit (Absolute)",
        value: configurationOrigin.ZoomLimits.Range.XRange.Max,
      },
    );
  }

  if (
    configurationOrigin?.MoveRamp !== undefined &&
    configurationOrigin?.MoveRamp !== null
  ) {
    infoItems.push({
      label: "Move Ramp",
      value: configurationOrigin.MoveRamp,
    });
  }

  if (
    configurationOrigin?.PresetRamp !== undefined &&
    configurationOrigin?.PresetRamp !== null
  ) {
    infoItems.push({
      label: "Preset Ramp",
      value: configurationOrigin.PresetRamp,
    });
  }

  if (
    configurationOrigin?.PresetTourRamp !== undefined &&
    configurationOrigin?.PresetTourRamp !== null
  ) {
    infoItems.push({
      label: "Preset Tour Ramp",
      value: configurationOrigin.PresetTourRamp,
    });
  }

  // Section state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [configurationUpdate, setConfigurationUpdate] = useState<any>(null);
  const [timeoutSeconds, setTimeoutSeconds] = useState<number | "">("");

  // Handlers
  const handleOpenDialog = () => {
    if (!configurationOrigin) return;

    setConfigurationUpdate(structuredClone(configurationOrigin));

    setTimeoutSeconds(
      configurationOrigin?.DefaultPTZTimeout
        ? getSecondsFromDuration(configurationOrigin?.DefaultPTZTimeout)
        : "",
    );

    setDialogOpen(true);
  };
  const handleDialogClose = () => {
    setDialogOpen(false);
  };

  const handleUpdateConfiguration = () => {
    if (!configurationOrigin || !configurationUpdate) {
      return;
    }

    const configuration = getChangedConfiguration(
      configurationOrigin,
      configurationUpdate,
    );

    if (timeoutSeconds !== "") {
      configuration.DefaultPTZTimeout = getDurationFromSeconds(timeoutSeconds);
    }

    setConfigurationMutation.mutate(
      {
        cameraIdentifier,
        params: {
          configuration,
          force_persistence: true, // will set with toggle later
        },
      },
      {
        onSuccess: () => {
          toast.success("PTZ configurations updated successfully");
          setDialogOpen(false);
        },
        onError: () => {
          toast.error("Failed to update PTZ configurations");
        },
      },
    );
  };

  const currentValues = useMemo(
    () => ({
      panSpeed: configurationUpdate?.DefaultPTZSpeed?.PanTilt?.x,
      tiltSpeed: configurationUpdate?.DefaultPTZSpeed?.PanTilt?.y,
      zoomSpeed: configurationUpdate?.DefaultPTZSpeed?.Zoom?.x,
      panMin: configurationUpdate?.PanTiltLimits?.Range?.XRange?.Min,
      panMax: configurationUpdate?.PanTiltLimits?.Range?.XRange?.Max,
      tiltMin: configurationUpdate?.PanTiltLimits?.Range?.YRange?.Min,
      tiltMax: configurationUpdate?.PanTiltLimits?.Range?.YRange?.Max,
      zoomMin: configurationUpdate?.ZoomLimits?.Range?.XRange?.Min,
      zoomMax: configurationUpdate?.ZoomLimits?.Range?.XRange?.Max,
      moveRamp: configurationUpdate?.MoveRamp,
      presetRamp: configurationUpdate?.PresetRamp,
      presetTourRamp: configurationUpdate?.PresetTourRamp,
      timeout: timeoutSeconds,
    }),
    [configurationUpdate, timeoutSeconds],
  );

  const originalValues = useMemo(
    () => ({
      panSpeed: configurationOrigin?.DefaultPTZSpeed?.PanTilt?.x,
      tiltSpeed: configurationOrigin?.DefaultPTZSpeed?.PanTilt?.y,
      zoomSpeed: configurationOrigin?.DefaultPTZSpeed?.Zoom?.x,
      panMin: configurationOrigin?.PanTiltLimits?.Range?.XRange?.Min,
      panMax: configurationOrigin?.PanTiltLimits?.Range?.XRange?.Max,
      tiltMin: configurationOrigin?.PanTiltLimits?.Range?.YRange?.Min,
      tiltMax: configurationOrigin?.PanTiltLimits?.Range?.YRange?.Max,
      zoomMin: configurationOrigin?.ZoomLimits?.Range?.XRange?.Min,
      zoomMax: configurationOrigin?.ZoomLimits?.Range?.XRange?.Max,
      moveRamp: configurationOrigin?.MoveRamp,
      presetRamp: configurationOrigin?.PresetRamp,
      presetTourRamp: configurationOrigin?.PresetTourRamp,
      timeout:
        configurationOrigin?.DefaultPTZTimeout != null
          ? getSecondsFromDuration(configurationOrigin.DefaultPTZTimeout)
          : "",
    }),
    [configurationOrigin],
  );

  const hasChanges = useFormChanges(currentValues, originalValues);

  return (
    <QueryWrapper
      isLoading={isLoading}
      isError={isError}
      errorMessage={
        error?.message || "Failed to load PTZ configurations information"
      }
      isEmpty={
        !ptzConfigurations ||
        ptzConfigurations.configurations.length === 0 ||
        !ptzConfigurationOptions
      }
      emptyMessage="No PTZ configurations information available"
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
          <Button
            size="small"
            startIcon={<GlobalFilters size={16} />}
            onClick={handleOpenDialog}
          >
            Configure
          </Button>
        </Box>

        {/* configurationOrigin Table */}
        <TableContainer>
          <Table
            size="small"
            sx={{
              [`& .${tableCellClasses.root}`]: {
                borderBottom: `1px solid ${theme.palette.divider}`,
              },
              "& tr:first-of-type td": {
                borderTop: `1px solid ${theme.palette.divider}`,
              },
            }}
          >
            <TableBody>
              {infoItems.map((item) => (
                <TableRow key={item.label}>
                  <TableCell
                    sx={{
                      py: 1,
                      pl: 0,
                      width: "60%",
                      color: "text.secondary",
                    }}
                  >
                    <Typography variant="body2">{item.label}</Typography>
                  </TableCell>
                  <TableCell sx={{ py: 1, pr: 0 }}>
                    <Typography variant="body2">{item.value}</Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>

        {/* PTZ configurationOrigin Dialog */}
        <Dialog
          open={dialogOpen}
          onClose={handleDialogClose}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>
            <Box
              display="flex"
              justifyContent="space-between"
              alignItems="center"
              gap={1}
            >
              <Typography variant="inherit">Configure PTZ</Typography>
              <Typography variant="caption" fontWeight="medium" color="primary">
                {`Node Token: ${configurationOrigin?.NodeToken}`}
              </Typography>
            </Box>
          </DialogTitle>
          <DialogContent>
            <Box
              sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}
            >
              {configurationOrigin?.DefaultPTZSpeed?.PanTilt && (
                <Stack spacing={2} direction="row">
                  <TextField
                    fullWidth
                    type="number"
                    label="Default Pan Speed (Absolute/Relative)"
                    value={configurationUpdate?.DefaultPTZSpeed?.PanTilt?.x}
                    inputProps={{
                      min: configurationOptions?.Spaces?.PanTiltSpeedSpace[0]
                        ?.XRange.Min,
                      max: configurationOptions?.Spaces?.PanTiltSpeedSpace[0]
                        ?.XRange.Max,
                      step: 0.1,
                    }}
                    onChange={(event) => {
                      setConfigurationUpdate((prev: any) => ({
                        ...prev,
                        DefaultPTZSpeed: {
                          ...prev.DefaultPTZSpeed,
                          PanTilt: {
                            ...prev.DefaultPTZSpeed.PanTilt,
                            x: Number(event.target.value),
                          },
                        },
                      }));
                    }}
                  />
                  <TextField
                    fullWidth
                    type="number"
                    label="Default Tilt Speed (Absolute/Relative)"
                    value={configurationUpdate?.DefaultPTZSpeed?.PanTilt?.y}
                    inputProps={{
                      min: configurationOptions?.Spaces?.PanTiltSpeedSpace[0]
                        ?.XRange.Min,
                      max: configurationOptions?.Spaces?.PanTiltSpeedSpace[0]
                        ?.XRange.Max,
                      step: 0.1,
                    }}
                    onChange={(event) => {
                      setConfigurationUpdate((prev: any) => ({
                        ...prev,
                        DefaultPTZSpeed: {
                          ...prev.DefaultPTZSpeed,
                          PanTilt: {
                            ...prev.DefaultPTZSpeed.PanTilt,
                            y: Number(event.target.value),
                          },
                        },
                      }));
                    }}
                  />
                </Stack>
              )}
              {configurationOrigin?.DefaultPTZSpeed?.Zoom && (
                <TextField
                  fullWidth
                  type="number"
                  label="Default Zoom Speed (Absolute/Relative)"
                  value={configurationUpdate?.DefaultPTZSpeed?.Zoom?.x}
                  inputProps={{
                    min: configurationOptions?.Spaces?.ZoomSpeedSpace[0]?.XRange
                      .Min,
                    max: configurationOptions?.Spaces?.ZoomSpeedSpace[0]?.XRange
                      .Max,
                    step: 0.1,
                  }}
                  onChange={(event) => {
                    setConfigurationUpdate((prev: any) => ({
                      ...prev,
                      DefaultPTZSpeed: {
                        ...prev.DefaultPTZSpeed,
                        Zoom: {
                          ...prev.DefaultPTZSpeed.Zoom,
                          x: Number(event.target.value),
                        },
                      },
                    }));
                  }}
                />
              )}
              {configurationOrigin?.DefaultPTZTimeout && (
                <TextField
                  fullWidth
                  type="number"
                  label="Default PTZ Timeout in seconds (Continuous)"
                  helperText="If the PTZ Node supports continuous movements, it shall specify a default timeout, after which the movement stops."
                  value={timeoutSeconds}
                  onChange={(event) => {
                    setTimeoutSeconds(
                      event.target.value === ""
                        ? ""
                        : Number(event.target.value),
                    );
                  }}
                  inputProps={{
                    min: getSecondsFromDuration(
                      configurationOptions?.PTZTimeout?.Min,
                    ),
                    max: getSecondsFromDuration(
                      configurationOptions?.PTZTimeout?.Max,
                    ),
                    step: 1,
                  }}
                />
              )}
              {configurationOrigin?.PanTiltLimits?.Range?.XRange && (
                <Stack spacing={2} direction="row">
                  <TextField
                    fullWidth
                    type="number"
                    label="Min. Pan Limit (Absolute)"
                    value={
                      configurationUpdate?.PanTiltLimits?.Range?.XRange?.Min
                    }
                    inputProps={{
                      min: configurationOptions?.Spaces
                        ?.AbsolutePanTiltPositionSpace[0]?.XRange.Min,
                      max: configurationOptions?.Spaces
                        ?.AbsolutePanTiltPositionSpace[0]?.XRange.Max,
                      step: 0.1,
                    }}
                    onChange={(event) => {
                      setConfigurationUpdate((prev: any) => ({
                        ...prev,
                        PanTiltLimits: {
                          ...prev.PanTiltLimits,
                          Range: {
                            ...prev.PanTiltLimits.Range,
                            XRange: {
                              ...prev.PanTiltLimits.Range.XRange,
                              Min: Number(event.target.value),
                            },
                          },
                        },
                      }));
                    }}
                  />
                  <TextField
                    fullWidth
                    type="number"
                    label="Max. Pan Limit (Absolute)"
                    value={
                      configurationUpdate?.PanTiltLimits?.Range?.XRange?.Max
                    }
                    inputProps={{
                      min: configurationOptions?.Spaces
                        ?.AbsolutePanTiltPositionSpace[0]?.XRange.Min,
                      max: configurationOptions?.Spaces
                        ?.AbsolutePanTiltPositionSpace[0]?.XRange.Max,
                      step: 0.1,
                    }}
                    onChange={(event) => {
                      setConfigurationUpdate((prev: any) => ({
                        ...prev,
                        PanTiltLimits: {
                          ...prev.PanTiltLimits,
                          Range: {
                            ...prev.PanTiltLimits.Range,
                            XRange: {
                              ...prev.PanTiltLimits.Range.XRange,
                              Max: Number(event.target.value),
                            },
                          },
                        },
                      }));
                    }}
                  />
                </Stack>
              )}
              {configurationOrigin?.PanTiltLimits?.Range?.YRange && (
                <Stack spacing={2} direction="row">
                  <TextField
                    fullWidth
                    type="number"
                    label="Min. Tilt Limit (Absolute)"
                    value={
                      configurationUpdate?.PanTiltLimits?.Range?.YRange?.Min
                    }
                    inputProps={{
                      min: configurationOptions?.Spaces
                        ?.AbsolutePanTiltPositionSpace[0]?.YRange.Min,
                      max: configurationOptions?.Spaces
                        ?.AbsolutePanTiltPositionSpace[0]?.YRange.Max,
                      step: 0.1,
                    }}
                    onChange={(event) => {
                      setConfigurationUpdate((prev: any) => ({
                        ...prev,
                        PanTiltLimits: {
                          ...prev.PanTiltLimits,
                          Range: {
                            ...prev.PanTiltLimits.Range,
                            YRange: {
                              ...prev.PanTiltLimits.Range.YRange,
                              Min: Number(event.target.value),
                            },
                          },
                        },
                      }));
                    }}
                  />
                  <TextField
                    fullWidth
                    type="number"
                    label="Max. Tilt Limit (Absolute)"
                    value={
                      configurationUpdate?.PanTiltLimits?.Range?.YRange?.Max
                    }
                    inputProps={{
                      min: configurationOptions?.Spaces
                        ?.AbsolutePanTiltPositionSpace[0]?.YRange.Min,
                      max: configurationOptions?.Spaces
                        ?.AbsolutePanTiltPositionSpace[0]?.YRange.Max,
                      step: 0.1,
                    }}
                    onChange={(event) => {
                      setConfigurationUpdate((prev: any) => ({
                        ...prev,
                        PanTiltLimits: {
                          ...prev.PanTiltLimits,
                          Range: {
                            ...prev.PanTiltLimits.Range,
                            YRange: {
                              ...prev.PanTiltLimits.Range.YRange,
                              Max: Number(event.target.value),
                            },
                          },
                        },
                      }));
                    }}
                  />
                </Stack>
              )}
              {configurationOrigin?.ZoomLimits?.Range?.XRange && (
                <Stack spacing={2} direction="row">
                  <TextField
                    fullWidth
                    type="number"
                    label="Min. Zoom Limit (Absolute)"
                    value={configurationUpdate?.ZoomLimits?.Range?.XRange?.Min}
                    inputProps={{
                      min: configurationOptions?.Spaces
                        ?.AbsoluteZoomPositionSpace[0]?.XRange.Min,
                      max: configurationOptions?.Spaces
                        ?.AbsoluteZoomPositionSpace[0]?.XRange.Max,
                      step: 0.1,
                    }}
                    onChange={(event) => {
                      setConfigurationUpdate((prev: any) => ({
                        ...prev,
                        ZoomLimits: {
                          ...prev.ZoomLimits,
                          Range: {
                            ...prev.ZoomLimits.Range,
                            XRange: {
                              ...prev.ZoomLimits.Range.XRange,
                              Min: Number(event.target.value),
                            },
                          },
                        },
                      }));
                    }}
                  />
                  <TextField
                    fullWidth
                    type="number"
                    label="Max. Zoom Limit (Absolute)"
                    value={configurationUpdate?.ZoomLimits?.Range?.XRange?.Max}
                    inputProps={{
                      min: configurationOptions?.Spaces
                        ?.AbsoluteZoomPositionSpace[0]?.XRange.Min,
                      max: configurationOptions?.Spaces
                        ?.AbsoluteZoomPositionSpace[0]?.XRange.Max,
                      step: 0.1,
                    }}
                    onChange={(event) => {
                      setConfigurationUpdate((prev: any) => ({
                        ...prev,
                        ZoomLimits: {
                          ...prev.ZoomLimits,
                          Range: {
                            ...prev.ZoomLimits.Range,
                            XRange: {
                              ...prev.ZoomLimits.Range.XRange,
                              Max: Number(event.target.value),
                            },
                          },
                        },
                      }));
                    }}
                  />
                </Stack>
              )}
              {configurationOrigin?.MoveRamp !== undefined &&
                configurationOrigin?.MoveRamp !== null && (
                  <TextField
                    fullWidth
                    type="number"
                    label="Move Ramp"
                    helperText="The optional acceleration ramp used by the device when moving."
                    value={configurationUpdate?.MoveRamp}
                    inputProps={{
                      min: 0,
                      step: 1, // Integer
                    }}
                    onChange={(event) => {
                      setConfigurationUpdate((prev: any) => ({
                        ...prev,
                        MoveRamp: Number(event.target.value),
                      }));
                    }}
                  />
                )}
              {configurationOrigin?.PresetRamp !== undefined &&
                configurationOrigin?.PresetRamp !== null && (
                  <TextField
                    fullWidth
                    type="number"
                    label="Preset Ramp"
                    helperText="The optional acceleration ramp used by the device when recalling presets."
                    value={configurationUpdate?.PresetRamp}
                    inputProps={{
                      min: 0,
                      step: 1, // Integer
                    }}
                    onChange={(event) => {
                      setConfigurationUpdate((prev: any) => ({
                        ...prev,
                        PresetRamp: Number(event.target.value),
                      }));
                    }}
                  />
                )}
              {configurationOrigin?.PresetTourRamp !== undefined &&
                configurationOrigin?.PresetTourRamp !== null && (
                  <TextField
                    fullWidth
                    type="number"
                    label="Preset Tour Ramp"
                    helperText="The optional acceleration ramp used by the device when executing PresetTours."
                    value={configurationUpdate?.PresetTourRamp}
                    inputProps={{
                      min: 0,
                      step: 1, // Integer
                    }}
                    onChange={(event) => {
                      setConfigurationUpdate((prev: any) => ({
                        ...prev,
                        PresetTourRamp: Number(event.target.value),
                      }));
                    }}
                  />
                )}
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleDialogClose}>Cancel</Button>
            <Button
              onClick={handleUpdateConfiguration}
              variant="contained"
              disabled={setConfigurationMutation.isPending || !hasChanges}
            >
              {setConfigurationMutation.isPending ? (
                <CircularProgress enableTrackSlot size={24} />
              ) : (
                "Save"
              )}
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </QueryWrapper>
  );
}
