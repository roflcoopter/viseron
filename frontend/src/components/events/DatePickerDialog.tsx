import Badge from "@mui/material/Badge";
import Dialog from "@mui/material/Dialog";
import { PickersDay, PickersDayProps } from "@mui/x-date-pickers/PickersDay";
import { StaticDatePicker } from "@mui/x-date-pickers/StaticDatePicker";
import {
  DateValidationError,
  PickerChangeHandlerContext,
} from "@mui/x-date-pickers/models";
import dayjs, { Dayjs } from "dayjs";

import { useFilteredCameras } from "components/camera/useCameraStore";
import { useEventsDatesOfInterest } from "lib/api/events";

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
  const eventsDateOfInterest = useEventsDatesOfInterest({
    camera_identifiers: Object.keys(filteredCameras),
    configOptions: {
      enabled: open,
    },
  });

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
            highlightedDays: eventsDateOfInterest.data?.dates_of_interest,
          } as any,
          actionBar: {
            actions: ["today", "cancel"],
          },
        }}
      />
    </Dialog>
  );
}
