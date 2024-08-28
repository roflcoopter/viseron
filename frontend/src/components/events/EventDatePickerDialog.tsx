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

import { useEventsAmountMultiple } from "lib/api/events";
import * as types from "lib/types";

import { useCameraStore } from "./utils";

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

export function getHighlightedDays(
  eventsAmount: types.EventsAmount["events_amount"],
) {
  const result: Record<string, number> = {};
  for (const [date, events] of Object.entries(eventsAmount)) {
    const totalEvents = Object.values(events).reduce((a, b) => a + b, 0);
    if (totalEvents > 0) {
      result[date] = totalEvents;
    }
  }
  return result;
}

type EventDatePickerDialogProps = {
  open: boolean;
  setOpen: (open: boolean) => void;
  date: Dayjs | null;
  onChange?: (
    value: Dayjs | null,
    context: PickerChangeHandlerContext<DateValidationError>,
  ) => void;
};

export function EventDatePickerDialog({
  open,
  setOpen,
  date,
  onChange,
}: EventDatePickerDialogProps) {
  const { selectedCameras } = useCameraStore();
  const eventsAmountQuery = useEventsAmountMultiple({
    camera_identifiers: selectedCameras,
    utc_offset_minutes: dayjs().utcOffset(),
  });
  const highlightedDays = useMemo(
    () =>
      eventsAmountQuery.data
        ? getHighlightedDays(eventsAmountQuery.data.events_amount)
        : {},
    [eventsAmountQuery.data],
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
