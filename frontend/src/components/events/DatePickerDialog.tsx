import Badge from "@mui/material/Badge";
import Dialog from "@mui/material/Dialog";
import { PickerDay, PickerDayProps } from "@mui/x-date-pickers/PickerDay";
import { StaticDatePicker } from "@mui/x-date-pickers/StaticDatePicker";
import {
  DateValidationError,
  PickerChangeHandlerContext,
} from "@mui/x-date-pickers/models";
import { Dayjs } from "dayjs";

import { DATE_FORMAT } from "lib/helpers/dates";

// Number of items per date, keyed by YYYY-MM-DD
export type HighlightedDays = Record<string, number>;

function HighlightedDay(
  props: PickerDayProps & {
    highlightedDays?: HighlightedDays;
  },
) {
  const { highlightedDays = {}, day, outsideCurrentMonth, ...other } = props;
  const dateString = day.format(DATE_FORMAT);
  const isSelected =
    !outsideCurrentMonth && Object.keys(highlightedDays).includes(dateString);
  return (
    <Badge
      key={day.toString()}
      overlap="circular"
      badgeContent={
        isSelected && highlightedDays[dateString] > 0
          ? highlightedDays[dateString]
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
      <PickerDay
        // eslint-disable-next-line react/jsx-props-no-spreading
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
  highlightedDays?: HighlightedDays;
  onChange?: (
    value: Dayjs | null,
    context: PickerChangeHandlerContext<DateValidationError>,
  ) => void;
};

export function DatePickerDialog({
  open,
  setOpen,
  date,
  highlightedDays,
  onChange,
}: DatePickerDialogProps) {
  const handleClose = () => {
    setOpen(false);
  };

  return (
    <Dialog open={open} onClose={handleClose}>
      <StaticDatePicker
        onChange={onChange}
        onAccept={handleClose}
        onClose={handleClose}
        value={date || undefined}
        slots={{
          day: HighlightedDay,
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
