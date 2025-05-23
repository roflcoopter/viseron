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

import { useFilteredCameras } from "components/camera/useCameraStore";
import { useTimespans } from "components/events/utils";
import { useEventsAmountMultiple } from "lib/api/events";
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
        isSelected && highlightedDays[date].events > 0
          ? highlightedDays[date].events
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
        sx={[
          isSelected
            ? {
                backgroundColor: "rgba(255, 99, 71, 0.4)",
              }
            : {
                backgroundColor: null,
              },
        ]}
      />
    </Badge>
  );
}

type HighlightedDays = {
  [date: string]: {
    events: number;
    timespanAvailable: boolean;
  };
};

export function getHighlightedDays(
  eventsAmount: types.EventsAmount["events_amount"],
  availableTimespans: types.HlsAvailableTimespan[],
) {
  const result: HighlightedDays = {};
  for (const timespan of availableTimespans) {
    // Loop through all dates between start and end
    const start = dayjs(timespan.start * 1000);
    const end = dayjs(timespan.end * 1000);
    for (let d = start; d.isBefore(end); d = d.add(1, "day")) {
      const date = d.format("YYYY-MM-DD");
      if (!(date in result)) {
        result[date] = {
          events: 0,
          timespanAvailable: true,
        };
      }
    }
  }

  for (const [date, events] of Object.entries(eventsAmount)) {
    const totalEvents = Object.values(events).reduce((a, b) => a + b, 0);
    if (totalEvents > 0) {
      if (!(date in result)) {
        result[date] = {
          events: totalEvents,
          timespanAvailable: false,
        };
      } else {
        result[date].events = totalEvents;
      }
    }
  }

  return result;
}

type DatePickerDialogProps = {
  open: boolean;
  setOpen: (open: boolean) => void;
  date: Dayjs | null;
  onChange?: (
    value: Dayjs | null,
    context: PickerChangeHandlerContext<DateValidationError>,
  ) => void;
};

export function DatePickerDialog({
  open,
  setOpen,
  date,
  onChange,
}: DatePickerDialogProps) {
  const filteredCameras = useFilteredCameras();
  const eventsAmountQuery = useEventsAmountMultiple({
    camera_identifiers: Object.keys(filteredCameras),
  });
  const { availableTimespans } = useTimespans(null, 5, open);
  const highlightedDays = useMemo(
    () =>
      eventsAmountQuery.data
        ? getHighlightedDays(
            eventsAmountQuery.data.events_amount,
            availableTimespans,
          )
        : {},
    [eventsAmountQuery.data, availableTimespans],
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
