import {
  CarFront,
  DocumentVideo,
  FaceActivated,
  Movement,
  TrashCan,
  WatsonHealth3DMprToggle,
} from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { alpha, useTheme } from "@mui/material/styles";
import { TimePicker } from "@mui/x-date-pickers/TimePicker";
import { Dayjs } from "dayjs";

import * as types from "lib/types";

interface RecordingHeaderDailyProps {
  camera: types.Camera | types.FailedCamera;
  date: string;
  totalVideos: number;
  startTime: Dayjs | null;
  endTime: Dayjs | null;
  triggerTypeFilter: string[];
  onStartTimeChange: (time: Dayjs | null) => void;
  onEndTimeChange: (time: Dayjs | null) => void;
  onClearTimes: () => void;
  onTriggerTypeChange: (
    event: React.MouseEvent<HTMLElement>,
    types: string[],
  ) => void;
}

export function RecordingHeaderDaily({
  camera,
  date,
  totalVideos,
  startTime,
  endTime,
  triggerTypeFilter,
  onStartTimeChange,
  onEndTimeChange,
  onClearTimes,
  onTriggerTypeChange,
}: RecordingHeaderDailyProps) {
  const theme = useTheme();

  return (
    <Box
      sx={{
        mb: 1,
        paddingX: 2,
        paddingY: 2,
        border: 2,
        borderColor: "divider",
        borderRadius: 1,
        backdropFilter: "blur(20px)",
        backgroundColor:
          theme.palette.mode === "dark"
            ? alpha(theme.palette.background.paper, 0.72)
            : "rgba(255,255,255,0.72)",
        boxShadow:
          theme.palette.mode === "dark"
            ? "0px 4px 16px rgba(0, 0, 0, 0.32), 0px 2px 4px rgba(0, 0, 0, 0.24)"
            : "0px 2px 8px rgba(0, 0, 0, 0.08), 0px 1px 2px rgba(0, 0, 0, 0.04)",
      }}
    >
      <Stack
        direction={{ xs: "column", md: "row" }}
        alignItems={{ xs: "flex-start", md: "center" }}
        justifyContent="space-between"
        spacing={1}
        sx={{ position: "relative" }}
      >
        <Stack direction="row" alignItems="center" spacing={2} flexWrap="wrap">
          <Stack direction="row" alignItems="center" spacing={1}>
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                color:
                  theme.palette.mode === "dark"
                    ? theme.palette.primary[300]
                    : theme.palette.primary.main,
              }}
            >
              <DocumentVideo size={24} />
            </Box>
            <Typography variant="h6">{camera.name}</Typography>
          </Stack>
          <Stack
            direction="row"
            alignItems="center"
            spacing={1}
            sx={{ display: { xs: "none", md: "flex" } }}
          >
            <Tooltip title="Stream resolution">
              <Chip
                label={`${camera.width} x ${camera.height}`}
                size="small"
                variant="outlined"
              />
            </Tooltip>
            <Tooltip title="Total videos">
              <Chip
                label={`${totalVideos} ${totalVideos === 1 ? "Video" : "Videos"}`}
                size="small"
                variant="outlined"
                color="info"
              />
            </Tooltip>
          </Stack>
        </Stack>

        <Stack
          direction="row"
          alignItems="center"
          spacing={1}
          flexWrap="wrap"
          sx={{ display: { xs: "flex", md: "none" } }}
        >
          <Tooltip title="Recording date">
            <Chip
              label={date}
              size="small"
              variant="outlined"
              color="primary"
            />
          </Tooltip>
          <Tooltip title="Stream resolution">
            <Chip
              label={`${camera.width} x ${camera.height}`}
              size="small"
              variant="outlined"
            />
          </Tooltip>
          <Tooltip title="Total videos">
            <Chip
              label={`${totalVideos} ${totalVideos === 1 ? "Video" : "Videos"}`}
              size="small"
              variant="outlined"
              color="info"
            />
          </Tooltip>
        </Stack>

        <ToggleButtonGroup
          value={triggerTypeFilter}
          onChange={onTriggerTypeChange}
          size="small"
          aria-label="trigger type filter"
          sx={{
            display: { xs: "flex", md: "none", lg: "flex" },
            position: { lg: "absolute" },
            left: { lg: "50%" },
            transform: { lg: "translateX(-50%)" },
            width: { xs: "100%", lg: "auto" },
            paddingTop: { xs: 1, md: 0 },
          }}
        >
          <Tooltip title="Motion Detection">
            <ToggleButton
              value="motion"
              aria-label="motion"
              sx={{ paddingX: 2, flex: { xs: 1, lg: "initial" } }}
            >
              <Movement size={20} />
            </ToggleButton>
          </Tooltip>
          <Tooltip title="Object Detection">
            <ToggleButton
              value="object"
              aria-label="object"
              sx={{ paddingX: 2, flex: { xs: 1, lg: "initial" } }}
            >
              <WatsonHealth3DMprToggle size={20} />
            </ToggleButton>
          </Tooltip>
          <Tooltip title="Face Recognition">
            <ToggleButton
              value="face_recognition"
              aria-label="face recognition"
              sx={{ paddingX: 2, flex: { xs: 1, lg: "initial" } }}
            >
              <FaceActivated size={20} />
            </ToggleButton>
          </Tooltip>
          <Tooltip title="License Plate Recognition">
            <ToggleButton
              value="license_plate_recognition"
              aria-label="license plate recognition"
              sx={{ paddingX: 2, flex: { xs: 1, lg: "initial" } }}
            >
              <CarFront size={20} />
            </ToggleButton>
          </Tooltip>
        </ToggleButtonGroup>

        <Stack
          paddingTop={{ xs: 1.5, md: 0 }}
          direction={{ xs: "column", sm: "row" }}
          alignItems={{ xs: "stretch", sm: "center" }}
          spacing={1}
          sx={{ width: { xs: "100%", sm: "auto" } }}
        >
          <TimePicker
            label="Start Time"
            value={startTime}
            onChange={onStartTimeChange}
            views={["hours", "minutes", "seconds"]}
            format="HH:mm:ss"
            slotProps={{
              textField: {
                size: "small",
                sx: {
                  minWidth: { xs: "100%", sm: 140 },
                  width: { xs: "100%", md: 180 },
                },
              },
            }}
          />
          <TimePicker
            label="End Time"
            value={endTime}
            onChange={onEndTimeChange}
            views={["hours", "minutes", "seconds"]}
            format="HH:mm:ss"
            slotProps={{
              textField: {
                size: "small",
                sx: {
                  minWidth: { xs: "100%", sm: 140 },
                  width: { xs: "100%", md: 180 },
                },
              },
            }}
          />
          {(startTime || endTime) && (
            <Tooltip title="Clear Time Range">
              <IconButton size="small" onClick={onClearTimes} color="error">
                <TrashCan size={20} />
              </IconButton>
            </Tooltip>
          )}
        </Stack>
      </Stack>
    </Box>
  );
}
