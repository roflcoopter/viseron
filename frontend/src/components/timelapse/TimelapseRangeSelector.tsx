import { CalendarHeatMap } from "@carbon/icons-react";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import { DateTimePicker } from "@mui/x-date-pickers/DateTimePicker";
import { Dayjs } from "dayjs";
import { useMemo, useState } from "react";

import { DatePickerDialog } from "components/events/DatePickerDialog";
import {
  DENSITY_OPTIONS,
  RANGE_PRESETS,
  TimelapseRange,
  TimelapseSelection,
  dayRange,
} from "components/timelapse/utils";
import { useTimelapseDatesOfInterest } from "lib/api/timelapse";
import {
  getDayjs,
  getDayjsFromUnixTimestamp,
  getDisplayDateTimeFormat,
  is12HourFormat,
} from "lib/helpers/dates";

type CustomRangeProps = {
  range: TimelapseRange;
  onApply: (range: TimelapseRange) => void;
};

function CustomRange({ range, onApply }: CustomRangeProps) {
  const [start, setStart] = useState<Dayjs | null>(
    getDayjsFromUnixTimestamp(range.start),
  );
  const [end, setEnd] = useState<Dayjs | null>(
    range.end === null ? getDayjs() : getDayjsFromUnixTimestamp(range.end),
  );
  const invalid = !start || !end || !end.isAfter(start);

  return (
    <Stack
      direction={{ xs: "column", sm: "row" }}
      spacing={2}
      alignItems={{ xs: "stretch", sm: "center" }}
    >
      <DateTimePicker
        label="Start"
        views={["year", "month", "day", "hours", "minutes", "seconds"]}
        value={start}
        onChange={setStart}
        closeOnSelect={false}
        ampm={is12HourFormat()}
        format={getDisplayDateTimeFormat()}
        slotProps={{ textField: { size: "small" } }}
      />
      <DateTimePicker
        label="End"
        views={["year", "month", "day", "hours", "minutes", "seconds"]}
        value={end}
        onChange={setEnd}
        closeOnSelect={false}
        ampm={is12HourFormat()}
        minDateTime={start || undefined}
        format={getDisplayDateTimeFormat()}
        slotProps={{ textField: { size: "small" } }}
      />
      <Button
        variant="contained"
        disabled={invalid}
        onClick={() => {
          if (start && end) {
            onApply({ start: start.unix(), end: end.unix() });
          }
        }}
      >
        Apply
      </Button>
    </Stack>
  );
}

type TimelapseRangeSelectorProps = {
  camera_identifier: string;
  selection: TimelapseSelection;
  range: TimelapseRange;
  density: number;
  onSelectionChange: (selection: TimelapseSelection) => void;
  onDensityChange: (density: number) => void;
};

export function TimelapseRangeSelector({
  camera_identifier,
  selection,
  range,
  density,
  onSelectionChange,
  onDensityChange,
}: TimelapseRangeSelectorProps) {
  const [customOpen, setCustomOpen] = useState(!selection.preset);
  const [dayPickerOpen, setDayPickerOpen] = useState(false);
  const datesOfInterest = useTimelapseDatesOfInterest({
    camera_identifier,
    configOptions: { enabled: dayPickerOpen },
  });
  const highlightedDays = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(datesOfInterest.data?.dates_of_interest ?? {}).map(
          ([day, { frames }]) => [day, frames],
        ),
      ),
    [datesOfInterest.data],
  );

  return (
    <Stack spacing={2}>
      <Stack
        direction="row"
        spacing={1}
        useFlexGap
        alignItems="center"
        sx={{ flexWrap: "wrap" }}
      >
        {RANGE_PRESETS.map((preset) => (
          <Chip
            key={preset.value}
            label={preset.label}
            color={selection.preset === preset.value ? "primary" : "default"}
            variant={selection.preset === preset.value ? "filled" : "outlined"}
            onClick={() => {
              setCustomOpen(false);
              onSelectionChange({ preset: preset.value });
            }}
          />
        ))}
        <Chip
          label="Custom"
          color={!selection.preset ? "primary" : "default"}
          variant={!selection.preset ? "filled" : "outlined"}
          onClick={() => setCustomOpen(!customOpen)}
        />
        <Tooltip title="Select day">
          <IconButton
            aria-label="Select day"
            onClick={() => setDayPickerOpen(true)}
          >
            <CalendarHeatMap size={20} />
          </IconButton>
        </Tooltip>
        <TextField
          select
          size="small"
          label="Frames"
          value={density}
          onChange={(event) => onDensityChange(Number(event.target.value))}
          sx={{ marginLeft: "auto", minWidth: 110 }}
        >
          {DENSITY_OPTIONS.map((option) => (
            <MenuItem key={option} value={option}>
              {option}
            </MenuItem>
          ))}
        </TextField>
      </Stack>
      {customOpen ? (
        <CustomRange
          // Reset the pickers when the range is changed elsewhere
          key={`${range.start}-${range.end}`}
          range={range}
          onApply={onSelectionChange}
        />
      ) : null}
      <DatePickerDialog
        open={dayPickerOpen}
        setOpen={setDayPickerOpen}
        date={getDayjsFromUnixTimestamp(range.start)}
        highlightedDays={highlightedDays}
        onChange={(value) => {
          setDayPickerOpen(false);
          if (value) {
            setCustomOpen(false);
            onSelectionChange(dayRange(value, getDayjs()));
          }
        }}
      />
    </Stack>
  );
}
