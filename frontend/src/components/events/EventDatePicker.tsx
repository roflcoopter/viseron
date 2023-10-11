import Badge from "@mui/material/Badge";
import Box from "@mui/material/Box";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { PickersDay, PickersDayProps } from "@mui/x-date-pickers/PickersDay";
import {
  DateValidationError,
  PickerChangeHandlerContext,
} from "@mui/x-date-pickers/models";
import dayjs, { Dayjs } from "dayjs";
import { useMemo } from "react";

import * as types from "lib/types";

function HasEvent(
  props: PickersDayProps<Dayjs> & { highlightedDays?: Record<string, any> }
) {
  const { highlightedDays = {}, day, outsideCurrentMonth, ...other } = props;

  const date = day.format("YYYY-MM-DD");
  const isSelected =
    !props.outsideCurrentMonth && Object.keys(highlightedDays).includes(date);
  return (
    <Badge
      key={props.day.toString()}
      overlap="circular"
      badgeContent={
        isSelected && highlightedDays[date] > 0
          ? highlightedDays[date]
          : undefined
      }
      max={9}
    >
      <PickersDay
        {...other}
        outsideCurrentMonth={outsideCurrentMonth}
        day={day}
        disabled={!isSelected}
        sx={{
          backgroundColor: isSelected ? "rgba(255, 99, 71, 0.4)" : undefined,
        }}
      />
    </Badge>
  );
}

type EventDatePickerProps = {
  date: Dayjs | null;
  recordings: types.RecordingsCamera;
  onChange?: (
    value: Dayjs | null,
    context: PickerChangeHandlerContext<DateValidationError>
  ) => void;
};

export function getHighlightedDays(recordings: types.RecordingsCamera) {
  const result: Record<string, number> = {};
  for (const date of Object.keys(recordings)) {
    result[date] = Object.keys(recordings[date]).length;
  }
  return result;
}

export function EventDatePicker({
  date,
  recordings,
  onChange,
}: EventDatePickerProps) {
  const highlightedDays = useMemo(
    () => getHighlightedDays(recordings),
    [recordings]
  );
  return (
    <Box
      sx={{
        width: "100%",
        padding: "10px",
        position: "sticky",
        top: 0,
        zIndex: 999,
        backgroundColor: (theme) => theme.palette.background.paper,
      }}
    >
      <DatePicker
        label="Date"
        format="YYYY-MM-DD"
        onChange={onChange}
        value={dayjs(date)}
        sx={{ width: "100%" }}
        slots={{
          day: HasEvent,
        }}
        slotProps={{
          day: {
            highlightedDays,
          } as any,
        }}
      />
    </Box>
  );
}
