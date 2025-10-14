import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Stack from "@mui/material/Stack";
import { DateTimePicker } from "@mui/x-date-pickers/DateTimePicker";
import { Dayjs } from "dayjs";
import { useState } from "react";

import { useFilteredCameras } from "components/camera/useCameraStore";
import { useExportTimespan } from "lib/commands";
import { is12HourFormat } from "lib/helpers";

type ExportDialogProps = {
  open: boolean;
  setOpen: (open: boolean) => void;
};

export function ExportDialog({ open, setOpen }: ExportDialogProps) {
  const [startDate, setStartDate] = useState<Dayjs | null>(null);
  const [endDate, setEndDate] = useState<Dayjs | null>(null);

  const filteredCameras = useFilteredCameras();
  const exportTimespan = useExportTimespan();

  const handleClose = () => {
    setOpen(false);
  };

  const handleStartDateAccept = (newValue: Dayjs | null) => {
    setStartDate(newValue);
    if (newValue && (!endDate || endDate.isBefore(newValue))) {
      setEndDate(newValue.add(5, "minute"));
    }
  };

  const handleExport = () => {
    if (!startDate || !endDate) return;
    exportTimespan(
      Object.keys(filteredCameras),
      startDate.unix(),
      endDate.unix(),
    );
    handleClose();
  };

  const isExportDisabled =
    !startDate || !endDate || endDate.isBefore(startDate);

  return (
    <Dialog fullWidth maxWidth="xs" open={open} onClose={handleClose}>
      <DialogTitle>Download Recording</DialogTitle>
      <DialogContent>
        <Stack spacing={3} sx={{ mt: 1 }}>
          <DateTimePicker
            label="Start Date & Time"
            views={["year", "month", "day", "hours", "minutes", "seconds"]}
            value={startDate}
            onAccept={handleStartDateAccept}
            onChange={handleStartDateAccept}
            closeOnSelect={false}
            ampm={is12HourFormat()}
          />
          <DateTimePicker
            label="End Date & Time"
            views={["year", "month", "day", "hours", "minutes", "seconds"]}
            value={endDate}
            onAccept={(newValue) => setEndDate(newValue)}
            onChange={handleStartDateAccept}
            closeOnSelect={false}
            ampm={is12HourFormat()}
            minDateTime={startDate || undefined}
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Button
          onClick={handleExport}
          disabled={isExportDisabled}
          variant="contained"
        >
          Download
        </Button>
      </DialogActions>
    </Dialog>
  );
}
