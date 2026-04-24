import { Save } from "@carbon/icons-react";
import Autocomplete from "@mui/material/Autocomplete";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import MenuItem from "@mui/material/MenuItem";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useMemo, useState } from "react";

import {
  useProfileAvailableTimezones,
  useProfileUpdatePreferences,
} from "lib/api/profile";
import {
  DATE_FORMAT,
  VALID_DATE_FORMATS,
  is12HourFormat,
} from "lib/helpers/dates";
import * as types from "lib/types";

export function Preferences({ user }: { user: types.AuthUserResponse }) {
  // Timezone
  const profileAvailableTimezonesQuery = useProfileAvailableTimezones();
  const savedTimezone = user.preferences?.timezone ?? null;
  const [selectedTimezone, setSelectedTimezone] = useState<string | null>(
    savedTimezone,
  );
  const detectedTimezone = useMemo(
    () => Intl.DateTimeFormat().resolvedOptions().timeZone,
    [],
  );

  // Date format
  const savedDateFormat = user.preferences?.date_format ?? null;
  const [selectedDateFormat, setSelectedDateFormat] = useState<string | null>(
    savedDateFormat,
  );

  // Time format
  const savedTimeFormat = user.preferences?.time_format ?? null;
  const [selectedTimeFormat, setSelectedTimeFormat] = useState<string | null>(
    savedTimeFormat,
  );
  const detectedTimeFormat = useMemo(
    () => (is12HourFormat() ? "12-hour" : "24-hour"),
    [],
  );

  // Preferences
  const profileUpdatePreferences = useProfileUpdatePreferences();
  const preferencesHasChanges =
    selectedTimezone !== savedTimezone ||
    selectedDateFormat !== savedDateFormat ||
    selectedTimeFormat !== savedTimeFormat;
  const handleSavePreferences = () => {
    profileUpdatePreferences.mutate({
      timezone: selectedTimezone,
      date_format: selectedDateFormat,
      time_format: selectedTimeFormat,
    });
  };
  return (
    <Box sx={{ marginBottom: 3 }}>
      <Typography variant="subtitle2" sx={{ marginBottom: 1 }}>
        Timezone
      </Typography>
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ marginBottom: 2 }}
      >
        Set your preferred timezone for displaying dates and times.
      </Typography>

      <Autocomplete
        value={selectedTimezone}
        onChange={(_event, newValue) => {
          setSelectedTimezone(newValue);
        }}
        options={profileAvailableTimezonesQuery.data?.timezones ?? []}
        loading={profileAvailableTimezonesQuery.isLoading}
        renderInput={(params) => (
          <TextField
            {...params}
            label="Timezone"
            placeholder="Select a timezone..."
            helperText={
              selectedTimezone
                ? " "
                : `Currently using your browser's auto-detected timezone: ${detectedTimezone}`
            }
          />
        )}
        isOptionEqualToValue={(option, value) => option === value}
        clearOnEscape
        autoHighlight
        sx={{ marginBottom: 2 }}
      />

      <Typography variant="subtitle2" sx={{ marginBottom: 1 }}>
        Date Format
      </Typography>
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ marginBottom: 2 }}
      >
        Set your preferred format for displaying dates.
      </Typography>

      <TextField
        select
        label="Date Format"
        value={selectedDateFormat ?? DATE_FORMAT}
        onChange={(e) => {
          const value = e.target.value;
          setSelectedDateFormat(value === DATE_FORMAT ? null : value);
        }}
        sx={{ marginBottom: 2, minWidth: 280 }}
      >
        {VALID_DATE_FORMATS.map((fmt) => (
          <MenuItem key={fmt.value} value={fmt.value}>
            {fmt.label}
          </MenuItem>
        ))}
      </TextField>

      <Typography variant="subtitle2" sx={{ marginBottom: 1 }}>
        Time Format
      </Typography>
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ marginBottom: 2 }}
      >
        Set your preferred format for displaying times.
      </Typography>

      <TextField
        select
        label="Time Format"
        value={selectedTimeFormat ?? ""}
        onChange={(e) => {
          const value = e.target.value;
          setSelectedTimeFormat(value === "" ? null : value);
        }}
        helperText={
          selectedTimeFormat
            ? " "
            : `Currently using your browser's auto-detected format: ${detectedTimeFormat}`
        }
        sx={{ marginBottom: 2, minWidth: 280 }}
      >
        <MenuItem value="">Auto (browser)</MenuItem>
        <MenuItem value="24h">24-hour (e.g. 14:30:00)</MenuItem>
        <MenuItem value="12h">12-hour (e.g. 2:30:00 PM)</MenuItem>
      </TextField>

      <Box sx={{ display: "flex", gap: 1 }}>
        <Button
          variant="contained"
          onClick={handleSavePreferences}
          disabled={!preferencesHasChanges}
          loading={profileUpdatePreferences.isPending}
          loadingPosition="start"
          startIcon={<Save />}
        >
          Save
        </Button>
      </Box>
    </Box>
  );
}
