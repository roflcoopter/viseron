import {
  ArrowDown,
  ArrowUp,
  Copy,
  FilterEdit,
  FilterRemove,
  PlayFilledAlt,
  Search,
  StopFilledAlt,
} from "@carbon/icons-react";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Fab,
  FormControl,
  InputAdornment,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useRef, useState } from "react";

import { Loading } from "components/loading/Loading";
import { useTitle } from "hooks/UseTitle";
import { useToast } from "hooks/UseToast";
import { LogEntry, useLogs } from "lib/api/logger";
import {
  getDayjsFromUnixTimestamp,
  getDisplayDateStringFromDayjs,
  getTimeStringFromDayjs,
} from "lib/helpers/dates";

const LOG_LEVELS = [
  { value: "", label: "All Levels" },
  { value: "critical", label: "Critical" },
  { value: "error", label: "Error" },
  { value: "warning", label: "Warning" },
  { value: "info", label: "Info" },
  { value: "debug", label: "Debug" },
];

const LINE_OPTIONS = [
  { value: 100, label: "100 lines" },
  { value: 500, label: "500 lines" },
  { value: 1000, label: "1000 lines" },
  { value: 2500, label: "2500 lines" },
  { value: 5000, label: "5000 lines" },
];

const levelColor = (level?: string) => {
  switch (level) {
    case "critical":
      return "error";
    case "error":
      return "error";
    case "warning":
      return "warning";
    case "info":
      return "info";
    case "debug":
      return "secondary";
    default:
      return "default";
  }
};

const levelBgColor = (level?: string) => {
  switch (level) {
    case "critical":
      return "background.paper";
    case "error":
      return "rgba(211, 47, 47, 0.08)";
    case "warning":
      return "rgba(237, 108, 2, 0.06)";
    case "info":
      return "rgba(2, 136, 209, 0.04)";
    case "debug":
      return "rgba(156, 39, 176, 0.04)";
    default:
      return "transparent";
  }
};

function formatLogTimestamp(timestamp_unix_ms: number): string | number {
  const d = getDayjsFromUnixTimestamp(timestamp_unix_ms);
  if (!d.isValid()) return timestamp_unix_ms;
  return `${getDisplayDateStringFromDayjs(d)} ${getTimeStringFromDayjs(d)}`;
}

function LogHeader() {
  return (
    <Box
      sx={{
        display: { xs: "none", md: "grid" },
        gridTemplateColumns: "140px 70px 310px minmax(0, 1fr)",
        gap: 1.5,
        px: 2,
        py: 1,

        position: "sticky",
        top: 0,
        zIndex: 10,

        backgroundColor: "background.paper",
        borderBottom: "1px solid",
        borderColor: "divider",

        fontSize: 11,
        fontWeight: 700,
        color: "text.secondary",
        textTransform: "uppercase",
      }}
    >
      <Box>TIMESTAMP</Box>
      <Box>LEVEL</Box>
      <Box>LOGGER</Box>
      <Box>MESSAGE</Box>
    </Box>
  );
}

function LogLine({ entry }: { entry: LogEntry }) {
  const theme = useTheme();

  const formattedTimestamp = entry.timestamp_unix_ms
    ? formatLogTimestamp(entry.timestamp_unix_ms)
    : null;

  return (
    <Box
      sx={{
        display: {
          xs: "flex",
          md: "grid",
        },

        flexDirection: {
          xs: "column",
        },

        gridTemplateColumns: {
          md: "140px 70px 310px minmax(0, 1fr)",
        },

        gap: {
          xs: 0.5,
          md: 1.5,
        },

        p: 1,
        px: 2,

        borderBottom: "1px solid",
        borderColor: "divider",

        fontFamily: "monospace", // to render code-style typography like in System Events
        fontSize: 12.5,
        backgroundColor: levelBgColor(entry.level),

        "&:hover": {
          backgroundColor: "action.hover",
        },
      }}
    >
      {/* Timestamp */}
      <Box
        sx={{
          color: "text.secondary",
          whiteSpace: "nowrap",
          fontSize: 11.5,
        }}
      >
        {formattedTimestamp}
      </Box>

      {/* Level */}
      <Box>
        {entry.level && (
          <Chip
            label={entry.level.toUpperCase()}
            size="small"
            color={levelColor(entry.level) as any}
            sx={{
              height: 18,
              fontSize: 10,
              fontWeight: 700,
              minWidth: 52,
            }}
          />
        )}
      </Box>

      {/* Logger */}
      <Box
        sx={{
          color: "primary",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: {
            xs: "normal",
            md: "nowrap",
          },
          minWidth: { xs: 0, md: 310 },
          fontWeight: 550,
        }}
        title={entry.name}
      >
        {entry.name}
      </Box>

      {/* Message */}
      <Box
        sx={{
          color: entry.unparsed
            ? theme.palette.text.secondary
            : theme.palette.text.primary,

          minWidth: 0,
          wordBreak: "break-word",
          overflowWrap: "anywhere",
          whiteSpace: "pre-wrap",
        }}
      >
        {entry.message || entry.raw}
      </Box>
    </Box>
  );
}

function Logs() {
  "use no memo";

  useTitle("Logs");
  const toast = useToast();
  const theme = useTheme();
  const autoScrollRef = useRef<HTMLDivElement>(null);
  const intervalRef = useRef<number | null>(null);

  const [lines, setLines] = useState<number>(500);
  const [search, setSearch] = useState<string>("");
  const [level, setLevel] = useState<string>("");
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [appliedSearch, setAppliedSearch] = useState<string>("");
  const [appliedLevel, setAppliedLevel] = useState<string>("");
  const hasInitialLoadCompleted = useRef(false);

  const {
    data: logsData,
    isLoading,
    refetch,
  } = useLogs(lines, appliedSearch || null, appliedLevel || null, {
    refetchOnWindowFocus: false,
  });

  // see https://github.com/TanStack/virtual/issues/1119 = no solution yet :(
  // eslint-disable-next-line react-hooks/incompatible-library -- opted out of memoization via "use no memo"
  const rowVirtualizer = useVirtualizer({
    count: logsData?.logs.length ?? 0,
    getScrollElement: () => autoScrollRef.current,
    estimateSize: () => 36,
    overscan: 15,
    useFlushSync: false,
  });

  const handleApplyFilters = () => {
    setAppliedSearch(search.trim() || "");
    setAppliedLevel(level);
  };

  const handleClearFilters = () => {
    setSearch("");
    setLevel("");
    setAppliedSearch("");
    setAppliedLevel("");
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleApplyFilters();
    }
  };

  const toggleAutoRefresh = () => {
    setAutoRefresh((prev) => !prev);
  };

  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = window.setInterval(() => {
        refetch();
      }, 3000);
    } else if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [autoRefresh, refetch]);

  if (!isLoading && !hasInitialLoadCompleted.current) {
    hasInitialLoadCompleted.current = true;
  }

  if (isLoading && !hasInitialLoadCompleted.current) {
    return <Loading text="Loading System Logs" />;
  }

  const scrollToTop = () => {
    rowVirtualizer.scrollToIndex(0, {
      align: "start",
      behavior: "auto",
    });
  };

  const scrollToBottom = () => {
    const logs = logsData?.logs;

    if (!logs?.length) return;

    rowVirtualizer.scrollToIndex(logs.length - 1, {
      align: "end",
      behavior: "auto",
    });
  };

  const handleCopyLogs = async () => {
    const logs = logsData?.logs;

    if (!logs?.length) return;

    const text = logs
      .map((entry) => {
        const timestamp = entry.timestamp_unix_ms
          ? formatLogTimestamp(entry.timestamp_unix_ms)
          : "";

        const log_level = entry.level?.toUpperCase() ?? "";
        const logger = entry.name ?? "";
        const message = entry.message || entry.raw || "";

        return `[${timestamp}] [${log_level}] [${logger}] ${message}`;
      })
      .join("\n");

    try {
      await navigator.clipboard.writeText(text);
      toast.success("Successfully copied current logs");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast.error(
        message ? `Failed to copy logs: ${message}` : "Failed to copy logs",
      );
    }
  };

  return (
    <Container
      sx={{
        paddingX: { xs: 1, md: 2 },
        paddingY: 0.5,

        height: `calc(
          99.5dvh -
          var(--header-height, ${theme.headerHeight}px) -
          ${theme.headerMargin}
        )`,

        display: "flex",
        flexDirection: "column",
        minHeight: 0,
      }}
    >
      <Paper variant="outlined" sx={{ p: 3, mb: 1, flexShrink: 0 }}>
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            mb: 2,
          }}
        >
          <Box>
            <Typography variant="h6">System Logs</Typography>
          </Box>
        </Box>

        <Stack gap={2}>
          <Box
            sx={{
              display: "flex",
              flexWrap: "wrap",
              gap: 2,
              alignItems: "flex-end",
            }}
          >
            {/* Latest Lines */}
            <FormControl
              sx={{
                minWidth: { md: 152 },
                flexGrow: { xs: 0.5, md: 0 },
              }}
            >
              <InputLabel>Latest Lines</InputLabel>
              <Select
                value={lines}
                label="Latest Lines"
                onChange={(e) => setLines(e.target.value as number)}
              >
                {LINE_OPTIONS.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {/* Level */}
            <FormControl
              sx={{
                minWidth: { md: 153 },
                flexGrow: { xs: 0.5, md: 0 },
              }}
            >
              <InputLabel shrink>Level</InputLabel>
              <Select
                value={level}
                label="Level"
                onChange={(e) => setLevel(e.target.value)}
                displayEmpty
                renderValue={(val) =>
                  LOG_LEVELS.find((l) => l.value === val)?.label || "All Levels"
                }
              >
                {LOG_LEVELS.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {/* Search */}
            <TextField
              label="Search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="Search in logs... <Enter>"
              sx={{
                minWidth: { md: 240 },
                flex: {
                  xs: "0 0 100%",
                  md: 1,
                },
              }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Search size={16} />
                  </InputAdornment>
                ),
              }}
            />
          </Box>
          <Stack direction={{ sm: "column", md: "row" }} sx={{ mb: 2, gap: 2 }}>
            <Button
              variant="contained"
              onClick={handleApplyFilters}
              startIcon={<FilterEdit size={16} />}
            >
              APPLY FILTERS
            </Button>

            <Button
              variant="contained"
              color="error"
              onClick={handleClearFilters}
              startIcon={<FilterRemove size={16} />}
            >
              CLEAR FILTERS
            </Button>

            {autoRefresh ? (
              <Button
                variant="contained"
                color="warning"
                onClick={toggleAutoRefresh}
                startIcon={<StopFilledAlt size={16} />}
              >
                STOP LIVE LOGGING
              </Button>
            ) : (
              <Button
                variant="contained"
                color="success"
                onClick={toggleAutoRefresh}
                startIcon={<PlayFilledAlt size={16} />}
              >
                START LIVE LOGGING
              </Button>
            )}
          </Stack>
        </Stack>
      </Paper>

      <Paper
        variant="outlined"
        sx={{
          overflow: "hidden",
          flex: 1,
          minHeight: 0,
          display: "flex",
          flexDirection: "column",
        }}
      >
        {isLoading ? (
          <Box
            display="flex"
            justifyContent="center"
            alignItems="center"
            sx={{
              flex: 1,
            }}
          >
            <CircularProgress enableTrackSlot />
          </Box>
        ) : logsData?.file_exists === false ? (
          <Box
            display="flex"
            justifyContent="center"
            alignItems="center"
            sx={{
              flex: 1,
            }}
          >
            <Typography>Log file not found.</Typography>
          </Box>
        ) : (
          <Box
            sx={{
              position: "relative",
              flex: 1,
              minHeight: 0,
              display: "flex",
              flexDirection: "column",
            }}
          >
            <Box
              ref={autoScrollRef}
              sx={{
                overflow: "auto",
                flex: 1,
                minHeight: 0,
              }}
              display={logsData?.logs.length === 0 ? "flex" : ""}
              justifyContent={logsData?.logs.length === 0 ? "center" : ""}
            >
              {logsData?.logs.length === 0 ? (
                <Box
                  display="flex"
                  justifyContent="center"
                  alignItems="center"
                  sx={{
                    flex: 1,
                  }}
                >
                  <Typography color="text.secondary" align="center">
                    No logs match the current filters
                  </Typography>
                </Box>
              ) : (
                <>
                  <LogHeader />

                  <Box
                    sx={{
                      height: `${rowVirtualizer.getTotalSize()}px`,
                      width: "100%",
                      position: "relative",
                    }}
                  >
                    {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                      const entry = logsData?.logs[virtualRow.index];

                      if (!entry) {
                        return null;
                      }

                      return (
                        <Box
                          key={entry.id}
                          data-index={virtualRow.index}
                          ref={rowVirtualizer.measureElement}
                          sx={{
                            position: "absolute",
                            top: 0,
                            left: 0,
                            width: "100%",
                            transform: `translateY(${virtualRow.start}px)`,
                          }}
                        >
                          <LogLine entry={entry} />
                        </Box>
                      );
                    })}
                  </Box>
                </>
              )}
            </Box>
            {logsData?.logs.length !== 0 && (
              <Stack
                spacing={1}
                sx={{
                  position: "absolute",
                  right: 16,
                  bottom: 16,
                  zIndex: 10,
                }}
              >
                <Tooltip title="Copy current logs" placement="left">
                  <Fab
                    size="small"
                    color="secondary"
                    onClick={handleCopyLogs}
                    aria-label="copy current logs"
                  >
                    <Copy />
                  </Fab>
                </Tooltip>

                <Tooltip title="Go to top" placement="left">
                  <Fab
                    size="small"
                    color="primary"
                    onClick={scrollToTop}
                    aria-label="go to top"
                  >
                    <ArrowUp />
                  </Fab>
                </Tooltip>

                <Tooltip title="Go to bottom" placement="left">
                  <Fab
                    size="small"
                    color="primary"
                    onClick={scrollToBottom}
                    aria-label="go to bottom"
                  >
                    <ArrowDown />
                  </Fab>
                </Tooltip>
              </Stack>
            )}
          </Box>
        )}
      </Paper>
    </Container>
  );
}

export default Logs;
