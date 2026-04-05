import { GlobalFilters, Help } from "@carbon/icons-react";
import {
  Autocomplete,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  FormHelperText,
  InputLabel,
  MenuItem,
  Select,
  Switch,
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
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { DateTimePicker } from "@mui/x-date-pickers/DateTimePicker";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { Dayjs } from "dayjs";
import { useEffect, useMemo, useState } from "react";

import { useAuthContext } from "context/AuthContext";
import { useToast } from "hooks/UseToast";
import { useFormChanges } from "hooks/useFormChanges";
import {
  useGetDeviceSystemDateAndTime,
  useSetDeviceSystemDateAndTime,
} from "lib/api/actions/onvif/device";
import { useProfileAvailableTimezones } from "lib/api/profile";
import { getDayjs, getDayjsFromOnvifDateTime } from "lib/helpers/dates";

import { QueryWrapper } from "../../config/QueryWrapper";

type TimeSource = "NTP" | "Browser" | "Manual" | "";

interface DeviceSystemDateAndTimeProps {
  cameraIdentifier: string;
}

export function DeviceSystemDateAndTime({
  cameraIdentifier,
}: DeviceSystemDateAndTimeProps) {
  const TITLE = "Date & Time";
  const DESC =
    "Manage ONVIF camera date and time settings. Browser Time is a time marker based on the timezone you select in your Viseron profile.";

  const theme = useTheme();
  const toast = useToast();
  const { user } = useAuthContext();

  // ONVIF API hooks
  const { data, dataUpdatedAt, isLoading, isError, error } =
    useGetDeviceSystemDateAndTime(cameraIdentifier);
  const setDateTimeMutation = useSetDeviceSystemDateAndTime(cameraIdentifier);

  const infoItems: { label: string; value: string | undefined }[] = [];

  // Section state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [timeSource, setTimeSource] = useState<TimeSource>("");
  const [daylightSavings, setDaylightSavings] = useState(false);
  const [timezone, setTimezone] = useState<string | null>(null);
  const [utcDateTime, setUtcDateTime] = useState<Dayjs>(getDayjs());

  // Store original values to detect changes
  const [originalValues, setOriginalValues] = useState<{
    timeSource: TimeSource;
    daylightSavings: boolean;
    timezone: string | null;
    utcDateTime: Dayjs;
  }>({
    timeSource: "",
    daylightSavings: false,
    timezone: null,
    utcDateTime: getDayjs().utc(),
  });

  const userTimezone = useMemo(
    () =>
      user?.preferences?.timezone ||
      Intl.DateTimeFormat().resolvedOptions().timeZone,
    [user?.preferences?.timezone],
  );

  const [currentTime, setCurrentTime] = useState(getDayjs());

  const profileAvailableTimezonesQuery = useProfileAvailableTimezones();

  // Format timezone options with UTC offset
  const timezoneOptions = useMemo(() => {
    if (!profileAvailableTimezonesQuery.data?.timezones) return [];

    return profileAvailableTimezonesQuery.data.timezones
      .map((tz) => {
        try {
          const offset = getDayjs().tz(tz).format("Z");
          return {
            label: `UTC${offset} ${tz}`,
            value: tz,
          };
        } catch {
          // Skip invalid timezones
          return null;
        }
      })
      .filter((tz): tz is { label: string; value: string } => tz !== null)
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [profileAvailableTimezonesQuery.data]);

  // Convert IANA timezone to simple POSIX format for backend
  const convertToPosix = (ianaTimezone: string | null): string | null => {
    if (!ianaTimezone) return null;

    try {
      const offset = getDayjs().tz(ianaTimezone).utcOffset();
      const hours = Math.floor(Math.abs(offset) / 60);
      const minutes = Math.abs(offset) % 60;

      // POSIX format uses inverted sign: negative offset means ahead of UTC
      const sign = offset >= 0 ? "-" : "+";

      // Use standard timezone abbreviation format for better ONVIF compatibility
      // Format: UTC{sign}{hours}[:{minutes}]
      if (minutes === 0) {
        return `UTC${sign}${hours}`;
      }
      return `UTC${sign}${hours}:${minutes.toString().padStart(2, "0")}`;
    } catch {
      return ianaTimezone;
    }
  };

  // Check if there are any changes
  const hasChanges = useFormChanges(
    { timeSource, daylightSavings, timezone, utcDateTime },
    originalValues,
    {
      timeSource: (current, original) => current === "" || current === original,
      utcDateTime: (current, original) => current.isSame(original),
    },
  );

  // Check if time source changed but timezone is still empty
  const timeSourceChanged =
    timeSource !== "" && timeSource !== originalValues.timeSource;
  const isTimezoneInvalid = timeSourceChanged && !timezone;

  // Store the last saved time to reduce delay after mutation
  const [lastSavedTime, setLastSavedTime] = useState<{
    utcTime: Dayjs;
    savedAt: number;
    timezone: string | null;
  } | null>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(getDayjs());
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const browserTime = useMemo(() => {
    try {
      return currentTime.tz(userTimezone).format("YYYY-MM-DD HH:mm:ss");
    } catch {
      return currentTime
        .tz(Intl.DateTimeFormat().resolvedOptions().timeZone)
        .format("YYYY-MM-DD HH:mm:ss");
    }
  }, [currentTime, userTimezone]);

  // Extract datetime data from API response
  if (data?.system_date) {
    const systemDate = data.system_date;
    if (typeof systemDate === "object" && systemDate !== null) {
      // DateTime Type
      const dateType = (systemDate as { DateTimeType?: string }).DateTimeType;
      if (dateType) {
        infoItems.push({ label: "DateTime Type", value: dateType });
      }
      // Daylight Savings
      const apiDaylightSavings = (systemDate as { DaylightSavings?: boolean })
        .DaylightSavings;
      if (apiDaylightSavings !== undefined) {
        infoItems.push({
          label: "Daylight Savings",
          value: apiDaylightSavings ? "Enabled" : "Disabled",
        });
      }
      // Timezone
      const apiTimezone = (systemDate as { TimeZone?: { TZ?: string } })
        .TimeZone?.TZ;
      if (apiTimezone) {
        infoItems.push({ label: "Timezone", value: apiTimezone });
      }
      // UTC Time
      const apiUtcDateTime = (
        systemDate as {
          UTCDateTime?: {
            Time?: { Hour?: number; Minute?: number; Second?: number };
            Date?: { Year?: number; Month?: number; Day?: number };
          };
        }
      ).UTCDateTime;
      if (apiUtcDateTime?.Time && apiUtcDateTime?.Date) {
        let formattedDateTime: string;

        if (lastSavedTime) {
          const elapsedMs = currentTime.valueOf() - lastSavedTime.savedAt;
          const updatedTime = lastSavedTime.utcTime.add(
            elapsedMs,
            "millisecond",
          );
          formattedDateTime = updatedTime.utc().format("YYYY-MM-DD HH:mm:ss");
        } else {
          const utcDate = getDayjsFromOnvifDateTime(apiUtcDateTime, true);
          const elapsedMs = currentTime.valueOf() - dataUpdatedAt;
          formattedDateTime = utcDate
            .add(elapsedMs, "millisecond")
            .utc()
            .format("YYYY-MM-DD HH:mm:ss");
        }

        infoItems.push({ label: "UTC Time", value: formattedDateTime });
      }
      // Camera Time
      const apiLocalDateTime = (
        systemDate as {
          LocalDateTime?: {
            Time?: { Hour?: number; Minute?: number; Second?: number };
            Date?: { Year?: number; Month?: number; Day?: number };
          };
        }
      ).LocalDateTime;

      // Display Camera Time from LocalDateTime or calculate from UTC + Timezone
      if (apiLocalDateTime?.Time && apiLocalDateTime?.Date) {
        let formattedDateTime: string;

        if (lastSavedTime && lastSavedTime.timezone) {
          try {
            const elapsedMs = currentTime.valueOf() - lastSavedTime.savedAt;
            const updatedTime = lastSavedTime.utcTime.add(
              elapsedMs,
              "millisecond",
            );
            formattedDateTime = updatedTime
              .tz(lastSavedTime.timezone)
              .format("YYYY-MM-DD HH:mm:ss");
          } catch {
            const elapsedMs = currentTime.valueOf() - dataUpdatedAt;
            formattedDateTime = getDayjsFromOnvifDateTime(apiLocalDateTime)
              .add(elapsedMs, "millisecond")
              .format("YYYY-MM-DD HH:mm:ss");
          }
        } else {
          const elapsedMs = currentTime.valueOf() - dataUpdatedAt;
          formattedDateTime = getDayjsFromOnvifDateTime(apiLocalDateTime)
            .add(elapsedMs, "millisecond")
            .format("YYYY-MM-DD HH:mm:ss");
        }

        infoItems.push({ label: "Camera Time", value: formattedDateTime });
      } else if (apiUtcDateTime?.Time && apiUtcDateTime?.Date && apiTimezone) {
        // Fallback: Calculate local time from UTC + Timezone
        try {
          let formattedDateTime: string;

          if (lastSavedTime && lastSavedTime.timezone) {
            const elapsedMs = currentTime.valueOf() - lastSavedTime.savedAt;
            const updatedTime = lastSavedTime.utcTime.add(
              elapsedMs,
              "millisecond",
            );
            formattedDateTime = updatedTime
              .tz(lastSavedTime.timezone)
              .format("YYYY-MM-DD HH:mm:ss");
          } else {
            const utcDate = getDayjsFromOnvifDateTime(apiUtcDateTime, true);
            const elapsedMs = currentTime.valueOf() - dataUpdatedAt;
            const updatedUtcTime = utcDate.add(elapsedMs, "millisecond");

            // Convert UTC to local time using timezone
            // Try to parse POSIX format (e.g., UTC+7, UTC-5:30)
            const posixMatch = apiTimezone.match(/UTC([+-])(\d+)(?::(\d+))?/);
            if (posixMatch) {
              const [, sign, hours, minutes = "0"] = posixMatch;
              const offsetMinutes =
                (parseInt(hours, 10) * 60 + parseInt(minutes, 10)) *
                (sign === "+" ? 1 : -1);
              formattedDateTime = updatedUtcTime
                .utcOffset(offsetMinutes)
                .format("YYYY-MM-DD HH:mm:ss");
            } else {
              // Try as IANA timezone
              formattedDateTime = updatedUtcTime
                .tz(apiTimezone)
                .format("YYYY-MM-DD HH:mm:ss");
            }
          }

          infoItems.push({ label: "Camera Time", value: formattedDateTime });
        } catch {
          // If timezone conversion fails, skip Camera Time
        }
      }

      // Browser Time (always shows current time in user's timezone)
      infoItems.push({ label: "Browser Time", value: browserTime });
    }
  }

  const handleEditDateTime = () => {
    // Store original values from camera for comparison, but don't pre-fill time source
    if (data?.system_date) {
      const systemDate = data.system_date as {
        DateTimeType?: string;
        DaylightSavings?: boolean;
        TimeZone?: { TZ?: string };
        UTCDateTime?: {
          Time?: { Hour?: number; Minute?: number; Second?: number };
          Date?: { Year?: number; Month?: number; Day?: number };
        };
      };

      let originalTimeSource: TimeSource = "";
      if (systemDate.DateTimeType === "NTP") {
        originalTimeSource = "NTP";
      } else if (systemDate.DateTimeType === "Manual") {
        originalTimeSource = "Manual";
      }

      // Don't pre-fill time source - let user choose
      setTimeSource("");
      setDaylightSavings(systemDate.DaylightSavings ?? false);
      setTimezone(systemDate.TimeZone?.TZ ?? null);

      // Pre-fill UTC DateTime if exists
      let dayjsObj: Dayjs;
      if (systemDate.UTCDateTime?.Time && systemDate.UTCDateTime?.Date) {
        dayjsObj = getDayjsFromOnvifDateTime(systemDate.UTCDateTime, true);
        setUtcDateTime(dayjsObj);
      } else {
        dayjsObj = getDayjs().utc();
        setUtcDateTime(dayjsObj);
      }

      setOriginalValues({
        timeSource: originalTimeSource,
        daylightSavings: systemDate.DaylightSavings ?? false,
        timezone: systemDate.TimeZone?.TZ ?? null,
        utcDateTime: dayjsObj,
      });
    }

    setDialogOpen(true);
  };

  const handleDialogClose = () => {
    setDialogOpen(false);
  };

  const handleSave = async () => {
    try {
      // Determine what changed
      const timezoneChanged = timezone !== originalValues.timezone;

      // Determine datetime_type to send (use current if changed, otherwise use original)
      let datetimeType: string;
      if (timeSourceChanged) {
        datetimeType = timeSource === "NTP" ? "NTP" : "Manual";
      } else {
        // Use original time source
        datetimeType = originalValues.timeSource === "NTP" ? "NTP" : "Manual";
      }

      let utcDateTimeObject;
      let timezoneValue: string | undefined;
      let savedUtcTime: Dayjs | null = null;

      // Send timezone if it changed (always, regardless of time source)
      if (timezoneChanged) {
        timezoneValue = convertToPosix(timezone) || undefined;
      }

      // Only send utc_datetime if time source changed to Browser or Manual
      if (timeSourceChanged) {
        if (timeSource === "NTP") {
          // NTP: clear lastSavedTime
          setLastSavedTime(null);
        } else if (timeSource === "Browser") {
          // Browser Time: send current browser time in UTC
          const now = getDayjs().utc();
          savedUtcTime = now;
          utcDateTimeObject = {
            Time: {
              Hour: now.hour(),
              Minute: now.minute(),
              Second: now.second(),
            },
            Date: {
              Year: now.year(),
              Month: now.month() + 1,
              Day: now.date(),
            },
          };
        } else if (timeSource === "Manual") {
          // Manual: send datetime from picker
          savedUtcTime = utcDateTime;
          utcDateTimeObject = {
            Time: {
              Hour: utcDateTime.hour(),
              Minute: utcDateTime.minute(),
              Second: utcDateTime.second(),
            },
            Date: {
              Year: utcDateTime.year(),
              Month: utcDateTime.month() + 1,
              Day: utcDateTime.date(),
            },
          };
        }
      }

      await setDateTimeMutation.mutateAsync({
        datetime_type: datetimeType,
        daylight_savings: daylightSavings,
        timezone: timezoneValue,
        utc_datetime: utcDateTimeObject,
      });

      // Update lastSavedTime after successful mutation
      if (savedUtcTime) {
        // Time was changed, store new UTC time with timezone
        setLastSavedTime({
          utcTime: savedUtcTime,
          savedAt: Date.now(),
          timezone,
        });
      } else if (timezoneChanged && !timeSourceChanged) {
        // Only timezone changed, preserve existing time but update timezone
        if (lastSavedTime) {
          setLastSavedTime({
            ...lastSavedTime,
            timezone,
          });
        } else {
          // No lastSavedTime yet, create from current API data
          const systemDate = data?.system_date as {
            UTCDateTime?: {
              Time?: { Hour?: number; Minute?: number; Second?: number };
              Date?: { Year?: number; Month?: number; Day?: number };
            };
          };
          if (systemDate?.UTCDateTime?.Time && systemDate?.UTCDateTime?.Date) {
            const currentUtcTime = getDayjsFromOnvifDateTime(
              systemDate.UTCDateTime,
              true,
            );
            setLastSavedTime({
              utcTime: currentUtcTime,
              savedAt: Date.now(),
              timezone,
            });
          }
        }
      }
      toast.success("Date and time settings updated successfully");
      handleDialogClose();
    } catch (err) {
      toast.error("Failed to update date and time settings");
    }
  };

  return (
    <QueryWrapper
      isLoading={isLoading}
      isError={isError}
      errorMessage={error?.message || "Failed to load date and time settings"}
      isEmpty={infoItems.length === 0}
      title={TITLE}
    >
      <Box>
        <Box
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          mb={1}
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
            onClick={handleEditDateTime}
          >
            Configure
          </Button>
        </Box>

        {/* System Date and Time Table */}
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
              {infoItems
                .filter((item) => item.value)
                .map((item) => (
                  <TableRow key={item.label}>
                    <TableCell
                      sx={{
                        py: 1,
                        pl: 0,
                        width: "36%",
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

        {/* Configure Date and Time Dialog */}
        <Dialog
          open={dialogOpen}
          onClose={handleDialogClose}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>Configure Date and Time</DialogTitle>
          <DialogContent>
            <Box
              sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}
            >
              {/* Timezone - Always visible, pre-filled from camera */}
              <Autocomplete
                value={
                  timezone
                    ? timezoneOptions.find((opt) => opt.value === timezone) ||
                      null
                    : null
                }
                onChange={(_event, newValue) => {
                  setTimezone(newValue ? newValue.value : null);
                }}
                options={timezoneOptions}
                getOptionLabel={(option) => option.label}
                loading={profileAvailableTimezonesQuery.isLoading}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Timezone"
                    placeholder="Select timezone..."
                    helperText="Device timezone in POSIX format"
                  />
                )}
                isOptionEqualToValue={(option, value) =>
                  option.value === value.value
                }
                clearOnEscape
                autoHighlight
              />

              {/* Time Source */}
              <FormControl fullWidth>
                <InputLabel>Time Source</InputLabel>
                <Select
                  value={timeSource}
                  label="Time Source"
                  onChange={(e) => setTimeSource(e.target.value as TimeSource)}
                  displayEmpty={false}
                >
                  <MenuItem value="NTP">Synchronize with NTP</MenuItem>
                  <MenuItem value="Browser">
                    Synchronize with Browser Time
                  </MenuItem>
                  <MenuItem value="Manual">Set Manually</MenuItem>
                </Select>
                <FormHelperText>
                  Set the source for the device&apos;s date and time
                </FormHelperText>
              </FormControl>

              {/* DateTimePicker - Only visible when Manual is selected */}
              {timeSource === "Manual" && (
                <LocalizationProvider dateAdapter={AdapterDayjs}>
                  <DateTimePicker
                    label="UTC Date and Time"
                    value={utcDateTime}
                    onChange={(newValue) => {
                      if (newValue) {
                        setUtcDateTime(newValue);
                      }
                    }}
                    views={[
                      "year",
                      "month",
                      "day",
                      "hours",
                      "minutes",
                      "seconds",
                    ]}
                    format="YYYY-MM-DD HH:mm:ss"
                    ampm={false}
                    slotProps={{
                      textField: {
                        fullWidth: true,
                        helperText: "Set the date and time in UTC",
                      },
                    }}
                  />
                </LocalizationProvider>
              )}

              {/* Daylight Savings */}
              <FormControlLabel
                control={
                  <Switch
                    checked={daylightSavings}
                    onChange={(e) => setDaylightSavings(e.target.checked)}
                  />
                }
                label="Daylight Savings"
              />
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleDialogClose}>Cancel</Button>
            <Button
              onClick={handleSave}
              variant="contained"
              disabled={
                setDateTimeMutation.isPending ||
                !hasChanges ||
                isTimezoneInvalid
              }
            >
              {setDateTimeMutation.isPending ? (
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
