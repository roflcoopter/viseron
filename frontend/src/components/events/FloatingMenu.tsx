import { CalendarHeatMap, Download, VideoAdd } from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Fab from "@mui/material/Fab";
import Tooltip from "@mui/material/Tooltip";
import { Dayjs } from "dayjs";
import { memo, useState } from "react";

import { CameraPickerDialog } from "components/camera/CameraPickerDialog";
import { DatePickerDialog } from "components/events/DatePickerDialog";
import { ExportDialog } from "components/events/ExportDialog";

type FloatingMenuProps = {
  date: Dayjs;
  setDate: (date: Dayjs) => void;
};

export const FloatingMenu = memo(({ date, setDate }: FloatingMenuProps) => {
  const [cameraDialogOpen, setCameraDialogOpen] = useState(false);
  const [dateDialogOpen, setDateDialogOpen] = useState(false);
  const [exportDialogOpen, setExportDialogOpen] = useState(false);

  return (
    <>
      <CameraPickerDialog
        open={cameraDialogOpen}
        setOpen={setCameraDialogOpen}
      />
      <DatePickerDialog
        open={dateDialogOpen}
        setOpen={setDateDialogOpen}
        date={date}
        onChange={(value) => {
          setDateDialogOpen(false);
          if (value) {
            setDate(value);
          }
        }}
      />
      <ExportDialog open={exportDialogOpen} setOpen={setExportDialogOpen} />
      <Box sx={{ position: "absolute", bottom: 16, right: 24 }}>
        <Tooltip title="Select Cameras">
          <Fab
            size="small"
            color="primary"
            onClick={() => setCameraDialogOpen(true)}
          >
            <VideoAdd size={20} />
          </Fab>
        </Tooltip>
        <Tooltip title="Select Date">
          <Fab
            size="small"
            color="primary"
            sx={{ marginLeft: 1 }}
            onClick={() => setDateDialogOpen(true)}
          >
            <CalendarHeatMap size={20} />
          </Fab>
        </Tooltip>
        <Tooltip title="Download">
          <Fab
            size="small"
            color="primary"
            sx={{ marginLeft: 1 }}
            onClick={() => setExportDialogOpen(true)}
          >
            <Download size={20} />
          </Fab>
        </Tooltip>
      </Box>
    </>
  );
});
