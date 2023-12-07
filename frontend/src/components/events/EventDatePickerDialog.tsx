import Badge from "@mui/material/Badge";
import Dialog from "@mui/material/Dialog";
import { PickersDay, PickersDayProps } from "@mui/x-date-pickers/PickersDay";
import { StaticDatePicker } from "@mui/x-date-pickers/StaticDatePicker";
import {
  DateValidationError,
  PickerChangeHandlerContext,
} from "@mui/x-date-pickers/models";
import dayjs, { Dayjs } from "dayjs";
import { useMemo } from "react";

import { useRecordings } from "lib/api/recordings";
import * as types from "lib/types";

function HasEvent(
  props: PickersDayProps<Dayjs> & { highlightedDays?: Record<string, any> },
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
      max={99}
      color="info"
      slotProps={{
        badge: {
          style: {
            fontSize: "0.7rem",
            top: "10%",
            height: "15px",
          },
        },
      }}
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

export function getHighlightedDays(recordings: types.RecordingsCamera) {
  const result: Record<string, number> = {};
  for (const date of Object.keys(recordings)) {
    result[date] = Object.keys(recordings[date]).length;
  }
  return result;
}

type EventDatePickerDialogProps = {
  open: boolean;
  setOpen: (open: boolean) => void;
  date: Dayjs | null;
  camera: types.Camera | null;
  onChange?: (
    value: Dayjs | null,
    context: PickerChangeHandlerContext<DateValidationError>,
  ) => void;
};

export function EventDatePickerDialog({
  open,
  setOpen,
  date,
  camera,
  onChange,
}: EventDatePickerDialogProps) {
  const recordingsQuery = useRecordings({
    camera_identifier: camera ? camera.identifier : null,
    configOptions: { enabled: !!camera },
  });
  const highlightedDays = useMemo(
    () =>
      recordingsQuery.data ? getHighlightedDays(recordingsQuery.data) : {},
    [recordingsQuery.data],
  );

  const handleClose = () => {
    setOpen(false);
  };

  return (
    <Dialog open={open} onClose={handleClose}>
      <StaticDatePicker
        onChange={onChange}
        onAccept={handleClose}
        onClose={handleClose}
        value={dayjs(date)}
        slots={{
          day: HasEvent,
        }}
        slotProps={{
          day: {
            highlightedDays,
          } as any,
          actionBar: {
            actions: ["today", "cancel"],
          },
        }}
      />
    </Dialog>
  );
}
