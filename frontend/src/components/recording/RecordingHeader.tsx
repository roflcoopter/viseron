import { Demo, TrashCan } from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { alpha, useTheme } from "@mui/material/styles";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { Dayjs } from "dayjs";

import { DATE_FORMAT } from "lib/helpers";
import * as types from "lib/types";

interface RecordingHeaderProps {
  camera: types.Camera | types.FailedCamera;
  totalDays: number;
  availableDates: string[];
  startDate: Dayjs | null;
  endDate: Dayjs | null;
  onStartDateChange: (date: Dayjs | null) => void;
  onEndDateChange: (date: Dayjs | null) => void;
  onClearDates: () => void;
}

export function RecordingHeader({
  camera,
  totalDays,
  availableDates,
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  onClearDates,
}: RecordingHeaderProps) {
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
              <Demo size={24} />
            </Box>
            <Typography variant="h6">{camera.name}</Typography>
          </Stack>
          <Stack
            direction="row"
            alignItems="center"
            spacing={1}
            sx={{ display: { xs: "none", md: "flex" } }}
          >
            {"connected" in camera && (
              <Tooltip title="Connection status">
                <Chip
                  label={camera.connected ? "Connected" : "Disconnected"}
                  size="small"
                  variant="outlined"
                  color={camera.connected ? "success" : "error"}
                />
              </Tooltip>
            )}
            <Tooltip title="Stream resolution">
              <Chip
                label={`${camera.width} x ${camera.height}`}
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
          {"connected" in camera && (
            <Tooltip title="Connection status">
              <Chip
                label={camera.connected ? "Connected" : "Disconnected"}
                size="small"
                variant="outlined"
                color={camera.connected ? "success" : "error"}
              />
            </Tooltip>
          )}
          <Tooltip title="Stream resolution">
            <Chip
              label={`${camera.width} x ${camera.height}`}
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
            onChange={onStartDateChange}
            format={DATE_FORMAT}
            shouldDisableDate={(date) => {
              const dateStr = date.format(DATE_FORMAT);
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
            onChange={onEndDateChange}
            format={DATE_FORMAT}
            shouldDisableDate={(date) => {
              const dateStr = date.format(DATE_FORMAT);
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
              <IconButton size="small" onClick={onClearDates} color="error">
                <TrashCan size={20} />
              </IconButton>
            </Tooltip>
          )}
        </Stack>
      </Stack>
    </Box>
  );
}
