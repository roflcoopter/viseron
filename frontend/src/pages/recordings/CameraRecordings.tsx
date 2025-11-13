import { Demo, TrashCan } from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Grow from "@mui/material/Grow";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { alpha, useTheme } from "@mui/material/styles";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import dayjs, { Dayjs } from "dayjs";
import { useState } from "react";
import { useParams } from "react-router-dom";
import ServerDown from "svg/undraw/server_down.svg?react";
import VoidSvg from "svg/undraw/void.svg?react";

import { ErrorMessage } from "components/error/ErrorMessage";
import { Loading } from "components/loading/Loading";
import RecordingCardDaily from "components/recording/RecordingCardDaily";
import { useTitle } from "hooks/UseTitle";
import { useCamera } from "lib/api/camera";
import { useRecordings } from "lib/api/recordings";
import { objHasValues } from "lib/helpers";
import * as types from "lib/types";

type CameraRecordingsParams = {
  camera_identifier: string;
};
function CameraRecordings() {
  const { camera_identifier } = useParams<
    keyof CameraRecordingsParams
  >() as CameraRecordingsParams;

  const theme = useTheme();

  const [startDate, setStartDate] = useState<Dayjs | null>(null);
  const [endDate, setEndDate] = useState<Dayjs | null>(null);

  const recordingsQuery = useRecordings({
    camera_identifier,
    latest: true,
    daily: true,
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
    !objHasValues<types.RecordingsCamera>(recordingsQuery.data)
  ) {
    return (
      <ErrorMessage
        text={`No recordings for ${cameraQuery.data.name}`}
        image={
          <VoidSvg width={150} height={150} role="img" aria-label="Void" />
        }
      />
    );
  }

  const availableDates = Object.keys(recordingsQuery.data);
  const totalDays = availableDates.length;
  const filteredDates =
    startDate && endDate
      ? availableDates.filter((date) => {
          const d = dayjs(date);
          return (
            (d.isAfter(startDate, "day") || d.isSame(startDate, "day")) &&
            (d.isBefore(endDate, "day") || d.isSame(endDate, "day"))
          );
        })
      : availableDates;

  const handleClearDates = () => {
    setStartDate(null);
    setEndDate(null);
  };

  return (
    <Container sx={{ paddingX: 2, paddingY: 1 }}>
      <Box
        sx={{
          position: "sticky",
          top: `${theme.headerHeight + 10}px`,
          zIndex: theme.zIndex.appBar - 1,
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
                <Demo size={24} />
              </Box>
              <Typography variant="h6">{cameraQuery.data.name}</Typography>
            </Stack>
            <Stack
              direction="row"
              alignItems="center"
              spacing={1}
              sx={{ display: { xs: "none", md: "flex" } }}
            >
              {"connected" in cameraQuery.data && (
                <Tooltip title="Connection status">
                  <Chip
                    label={
                      cameraQuery.data.connected ? "Connected" : "Disconnected"
                    }
                    size="small"
                    variant="outlined"
                    color={cameraQuery.data.connected ? "success" : "error"}
                  />
                </Tooltip>
              )}
              <Tooltip title="Stream resolution">
                <Chip
                  label={`${cameraQuery.data.width} x ${cameraQuery.data.height}`}
                  size="small"
                  variant="outlined"
                />
              </Tooltip>
              <Tooltip title="Total recording days">
                <Chip
                  label={`${totalDays} ${totalDays === 1 ? "Day" : "Days"}`}
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
            {"connected" in cameraQuery.data && (
              <Tooltip title="Connection status">
                <Chip
                  label={
                    cameraQuery.data.connected ? "Connected" : "Disconnected"
                  }
                  size="small"
                  variant="outlined"
                  color={cameraQuery.data.connected ? "success" : "error"}
                />
              </Tooltip>
            )}
            <Tooltip title="Stream resolution">
              <Chip
                label={`${cameraQuery.data.width} x ${cameraQuery.data.height}`}
                size="small"
                variant="outlined"
              />
            </Tooltip>
            <Tooltip title="Total recording days">
              <Chip
                label={`${totalDays} ${totalDays === 1 ? "Day" : "Days"}`}
                size="small"
                variant="outlined"
                color="info"
              />
            </Tooltip>
          </Stack>

          <Stack
            paddingTop={{ xs: 1.5, md: 0 }}
            direction={{ xs: "column", sm: "row" }}
            alignItems={{ xs: "stretch", sm: "center" }}
            spacing={1}
            sx={{ width: { xs: "100%", sm: "auto" } }}
          >
            <DatePicker
              label="Start Date"
              value={startDate}
              onChange={(newValue) => setStartDate(newValue)}
              format="YYYY-MM-DD"
              shouldDisableDate={(date) => {
                const dateStr = date.format("YYYY-MM-DD");
                return !availableDates.includes(dateStr);
              }}
              slotProps={{
                textField: {
                  size: "small",
                  sx: { minWidth: { xs: "100%", sm: 150 } },
                },
              }}
            />
            <DatePicker
              label="End Date"
              value={endDate}
              onChange={(newValue) => setEndDate(newValue)}
              format="YYYY-MM-DD"
              shouldDisableDate={(date) => {
                const dateStr = date.format("YYYY-MM-DD");
                return !availableDates.includes(dateStr);
              }}
              slotProps={{
                textField: {
                  size: "small",
                  sx: { minWidth: { xs: "100%", sm: 150 } },
                },
              }}
            />
            {(startDate || endDate) && (
              <Tooltip title="Clear Date Range">
                <IconButton
                  size="small"
                  onClick={handleClearDates}
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
        {filteredDates
          .sort()
          .reverse()
          .map((date) => (
            <Grow in appear key={date}>
              <Grid
                key={date}
                size={{
                  xs: 12,
                  sm: 12,
                  md: 6,
                  lg: 4,
                  xl: 3,
                }}
              >
                <RecordingCardDaily
                  camera={cameraQuery.data}
                  recording={Object.values(recordingsQuery.data[date])[0]}
                  date={date}
                />
              </Grid>
            </Grow>
          ))}
      </Grid>
    </Container>
  );
}

export default CameraRecordings;
