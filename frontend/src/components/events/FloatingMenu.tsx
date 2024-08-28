import CalendarMonthIcon from "@mui/icons-material/CalendarMonth";
import VideocamIcon from "@mui/icons-material/Videocam";
import Box from "@mui/material/Box";
import Fab from "@mui/material/Fab";
import Tooltip from "@mui/material/Tooltip";
import { Dayjs } from "dayjs";
import { memo, useState } from "react";

import { CameraPickerDialog } from "components/events/CameraPickerDialog";
import { EventDatePickerDialog } from "components/events/EventDatePickerDialog";
import * as types from "lib/types";

type FloatingMenuProps = {
  cameras: types.CamerasOrFailedCameras;
  date: Dayjs | null;
  setDate: (date: Dayjs | null) => void;
};

export const FloatingMenu = memo(
  ({ cameras, date, setDate }: FloatingMenuProps) => {
    const [cameraDialogOpen, setCameraDialogOpen] = useState(false);
    const [dateDialogOpen, setDateDialogOpen] = useState(false);

    return (
      <>
        <CameraPickerDialog
          open={cameraDialogOpen}
          setOpen={setCameraDialogOpen}
          cameras={cameras}
        />
        <EventDatePickerDialog
          open={dateDialogOpen}
          setOpen={setDateDialogOpen}
          date={date}
          onChange={(value) => {
            setDateDialogOpen(false);
            setDate(value);
          }}
        />
        <Box sx={{ position: "absolute", bottom: 14, right: 24 }}>
          <Tooltip title="Select Camera">
            <Fab
              size="medium"
              color="primary"
              onClick={() => setCameraDialogOpen(true)}
            >
              <VideocamIcon />
            </Fab>
          </Tooltip>
          <Tooltip title="Select Date">
            <Fab
              size="medium"
              color="primary"
              sx={{ marginLeft: 1 }}
              onClick={() => setDateDialogOpen(true)}
            >
              <CalendarMonthIcon />
            </Fab>
          </Tooltip>
        </Box>
      </>
    );
  },
);
