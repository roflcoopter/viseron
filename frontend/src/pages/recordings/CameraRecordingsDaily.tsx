import {
  CarFront,
  CenterSquare,
  DocumentVideo,
  FaceActivated,
  Movement,
  TrashCan,
} from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Grow from "@mui/material/Grow";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { alpha, useTheme } from "@mui/material/styles";
import { TimePicker } from "@mui/x-date-pickers/TimePicker";
import dayjs, { Dayjs } from "dayjs";
import { useState } from "react";
import { useParams } from "react-router-dom";
import ServerDown from "svg/undraw/server_down.svg?react";
import VoidSvg from "svg/undraw/void.svg?react";

import { ErrorMessage } from "components/error/ErrorMessage";
import { Loading } from "components/loading/Loading";
import RecordingCard from "components/recording/RecordingCard";
import { useTitle } from "hooks/UseTitle";
import { useCamera } from "lib/api/camera";
import { useRecordings } from "lib/api/recordings";
import { objHasValues } from "lib/helpers";
import * as types from "lib/types";

type CameraRecordingsDailyParams = {
  camera_identifier: string;
  date: string;
};
function CameraRecordingsDaily() {
  const { camera_identifier, date } = useParams<
    keyof CameraRecordingsDailyParams
  >() as CameraRecordingsDailyParams;

  const theme = useTheme();

  const [startTime, setStartTime] = useState<Dayjs | null>(null);
  const [endTime, setEndTime] = useState<Dayjs | null>(null);
  const [triggerTypeFilter, setTriggerTypeFilter] = useState<string[]>([]);

  const recordingsQuery = useRecordings({
    camera_identifier,
    date,
    failed: true,
  });
  const cameraQuery = useCamera(camera_identifier, true);

  useTitle(
    `Recordings${cameraQuery.data ? ` | ${cameraQuery.data.name}` : ""}`,
  );

  if (recordingsQuery.isError || cameraQuery.isError) {
    return (
      <ErrorMessage
        text="Error loading recordings"
        subtext={recordingsQuery.error?.message || cameraQuery.error?.message}
        image={
          <ServerDown width={150} height={150} role="img" aria-label="Void" />
        }
      />
    );
  }

  if (recordingsQuery.isPending || cameraQuery.isPending) {
    return <Loading text="Loading Recordings" />;
  }

  if (
    !recordingsQuery.data ||
    !objHasValues<types.RecordingsCamera>(recordingsQuery.data) ||
    !objHasValues(recordingsQuery.data[date])
  ) {
    return (
      <ErrorMessage
        text={`No recordings for ${cameraQuery.data.name} - ${date}`}
        image={
          <VoidSvg width={150} height={150} role="img" aria-label="Void" />
        }
      />
    );
  }

  const allRecordings = Object.keys(recordingsQuery.data[date]);
  const totalVideos = allRecordings.length;

  const filteredRecordings =
    startTime && endTime
      ? allRecordings.filter((recording) => {
          const recordingData = recordingsQuery.data[date][recording];
          const recordingTime = dayjs(recordingData.start_time);
          const timeMatch =
            (recordingTime.isAfter(startTime) ||
              recordingTime.isSame(startTime)) &&
            (recordingTime.isBefore(endTime) || recordingTime.isSame(endTime));

          const triggerTypeMatch =
            triggerTypeFilter.length === 0 ||
            (recordingData.trigger_type &&
              triggerTypeFilter.includes(recordingData.trigger_type));

          return timeMatch && triggerTypeMatch;
        })
      : allRecordings.filter((recording) => {
          const recordingData = recordingsQuery.data[date][recording];
          return (
            triggerTypeFilter.length === 0 ||
            (recordingData.trigger_type &&
              triggerTypeFilter.includes(recordingData.trigger_type))
          );
        });

  const handleStartTimeChange = (newValue: Dayjs | null) => {
    if (newValue) {
      // Set time with the correct date context
      const timeWithDate = dayjs(date)
        .hour(newValue.hour())
        .minute(newValue.minute())
        .second(newValue.second());
      setStartTime(timeWithDate);
    } else {
      setStartTime(null);
    }
  };

  const handleEndTimeChange = (newValue: Dayjs | null) => {
    if (newValue) {
      // Set time with the correct date context
      const timeWithDate = dayjs(date)
        .hour(newValue.hour())
        .minute(newValue.minute())
        .second(newValue.second());
      setEndTime(timeWithDate);
    } else {
      setEndTime(null);
    }
  };

  const handleClearTimes = () => {
    setStartTime(null);
    setEndTime(null);
  };

  const handleTriggerTypeChange = (
    _event: React.MouseEvent<HTMLElement>,
    newTypes: string[],
  ) => {
    setTriggerTypeFilter(newTypes);
  };

  return (
    <Container sx={{ paddingX: 2 }}>
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
          <Stack
            direction="row"
            alignItems="center"
            spacing={2}
            flexWrap="wrap"
          >
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
              <Typography variant="h6">{cameraQuery.data.name}</Typography>
            </Stack>
            <Stack
              direction="row"
              alignItems="center"
              spacing={1}
              sx={{ display: { xs: "none", md: "flex" } }}
            >
              <Tooltip title="Stream resolution">
                <Chip
                  label={`${cameraQuery.data.width} x ${cameraQuery.data.height}`}
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
                label={`${cameraQuery.data.width} x ${cameraQuery.data.height}`}
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
            onChange={handleTriggerTypeChange}
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
                <CenterSquare size={20} />
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
              onChange={handleStartTimeChange}
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
              onChange={handleEndTimeChange}
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
                <IconButton
                  size="small"
                  onClick={handleClearTimes}
                  color="error"
                >
                  <TrashCan size={20} />
                </IconButton>
              </Tooltip>
            )}
          </Stack>
        </Stack>
      </Box>

      <Grid container direction="row" spacing={1}>
        {filteredRecordings.reverse().map((recording) => (
          <Grow in appear key={recording}>
            <Grid
              key={recording}
              size={{
                xs: 12,
                sm: 12,
                md: 6,
                lg: 4,
                xl: 3,
              }}
            >
              <RecordingCard
                camera={cameraQuery.data}
                recording={recordingsQuery.data[date][recording]}
              />
            </Grid>
          </Grow>
        ))}
      </Grid>
    </Container>
  );
}

export default CameraRecordingsDaily;
