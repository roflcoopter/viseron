import CalendarMonthIcon from "@mui/icons-material/CalendarMonth";
import FilterAltIcon from "@mui/icons-material/FilterAlt";
import VideocamIcon from "@mui/icons-material/Videocam";
import TabContext from "@mui/lab/TabContext";
import TabList from "@mui/lab/TabList";
import TabPanel from "@mui/lab/TabPanel";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Container from "@mui/material/Container";
import SpeedDial from "@mui/material/SpeedDial";
import SpeedDialAction from "@mui/material/SpeedDialAction";
import Tab from "@mui/material/Tab";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import { Dayjs } from "dayjs";
import Hls from "hls.js";
import { SyntheticEvent, memo, useEffect, useRef, useState } from "react";

import { CameraPickerDialog } from "components/events/CameraPickerDialog";
import { EventDatePickerDialog } from "components/events/EventDatePickerDialog";
import { PlayerCard } from "components/events/EventPlayerCard";
import { EventTable } from "components/events/EventTable";
import { EventsCameraGrid } from "components/events/EventsCameraGrid";
import { TimelineTable } from "components/events/timeline/TimelineTable";
import { insertURLParameter } from "lib/helpers";
import * as types from "lib/types";

type FiltersProps = {
  cameras: types.Cameras;
  selectedCamera: types.Camera | null;

  date: Dayjs | null;
  setDate: (date: Dayjs | null) => void;

  changeSelectedCamera: (
    ev: React.MouseEvent<HTMLButtonElement, MouseEvent>,
    camera: types.Camera,
  ) => void;
};

const Filters = memo(
  ({
    cameras,
    selectedCamera,
    date,
    setDate,
    changeSelectedCamera,
  }: FiltersProps) => {
    const [open, setOpen] = useState(false);
    const [cameraDialogOpen, setCameraDialogOpen] = useState(false);
    const [dateDialogOpen, setDateDialogOpen] = useState(false);
    const theme = useTheme();

    const handleClose = () => {
      setOpen(false);
    };

    const handleClick = () => {
      setOpen(!open);
    };

    return (
      <>
        <CameraPickerDialog
          open={cameraDialogOpen}
          setOpen={setCameraDialogOpen}
          cameras={cameras}
          changeSelectedCamera={changeSelectedCamera}
          selectedCamera={selectedCamera}
        />
        <EventDatePickerDialog
          open={dateDialogOpen}
          setOpen={setDateDialogOpen}
          date={date}
          camera={selectedCamera}
          onChange={(value) => {
            setDateDialogOpen(false);
            setDate(value);
          }}
        />
        <SpeedDial
          ariaLabel="Filters"
          sx={{ position: "absolute", bottom: 16, right: 16 }}
          icon={<FilterAltIcon />}
          onClose={handleClose}
          onClick={handleClick}
          open={open}
        >
          <SpeedDialAction
            icon={<VideocamIcon />}
            tooltipTitle={"Select camera"}
            onClick={() => setCameraDialogOpen(true)}
            FabProps={{
              size: "medium",
              sx: { backgroundColor: theme.palette.primary.main },
            }}
          />
          <SpeedDialAction
            icon={<CalendarMonthIcon />}
            tooltipTitle={"Select date"}
            onClick={() => setDateDialogOpen(true)}
            FabProps={{
              size: "medium",
              sx: { backgroundColor: theme.palette.primary.main },
            }}
          />
        </SpeedDial>
      </>
    );
  },
);

type TabsProps = {
  parentRef: React.MutableRefObject<HTMLDivElement | null>;
  hlsRef: React.MutableRefObject<Hls | null>;
  date: Dayjs | null;
  selectedTab: "events" | "timeline";
  setSelectedTab: (tab: "events" | "timeline") => void;
  selectedCamera: types.Camera | null;
  selectedRecording: types.Recording | null;
  setSelectedRecording: (recording: types.Recording) => void;
  setRequestedTimestamp: (timestamp: number | null) => void;
};
const Tabs = ({
  parentRef,
  hlsRef,
  date,
  selectedTab,
  setSelectedTab,
  selectedCamera,
  selectedRecording,
  setSelectedRecording,
  setRequestedTimestamp,
}: TabsProps) => {
  const handleTabChange = (
    event: SyntheticEvent,
    tab: "events" | "timeline",
  ) => {
    setSelectedTab(tab);
  };

  useEffect(() => {
    insertURLParameter("tab", selectedTab);
  }, [selectedTab]);

  return (
    <TabContext value={selectedTab}>
      <Box
        sx={{
          borderBottom: 1,
          borderColor: "divider",
          display: "flex",
          justifyContent: "space-evenly",
        }}
      >
        <TabList onChange={handleTabChange} sx={{ width: "100%" }}>
          <Tab label="Events" value="events" sx={{ width: "50%" }} />
          <Tab label="Timeline" value="timeline" sx={{ width: "50%" }} />
        </TabList>
      </Box>
      <TabPanel value="events" sx={{ padding: 0, paddingTop: "5px" }}>
        {selectedCamera ? (
          <EventTable
            camera={selectedCamera}
            date={date}
            selectedRecording={selectedRecording}
            setSelectedRecording={setSelectedRecording}
          />
        ) : (
          <Typography align="center" sx={{ marginTop: "20px" }}>
            Select a camera to load Events
          </Typography>
        )}
      </TabPanel>
      <TabPanel value="timeline" sx={{ padding: 0, paddingTop: "5px" }}>
        {selectedCamera ? (
          <TimelineTable
            // Force re-render when camera or date changes
            key={`${selectedCamera.identifier}-${date?.unix().toString()}`}
            parentRef={parentRef}
            hlsRef={hlsRef}
            camera={selectedCamera}
            date={date}
            setRequestedTimestamp={setRequestedTimestamp}
          />
        ) : (
          <Typography align="center" sx={{ marginTop: "20px" }}>
            Select a camera to load Timeline
          </Typography>
        )}
      </TabPanel>
    </TabContext>
  );
};

type LayoutProps = {
  cameras: types.Cameras;
  selectedCamera: types.Camera | null;
  selectedRecording: types.Recording | null;
  setSelectedRecording: (recording: types.Recording) => void;
  changeSelectedCamera: (
    ev: React.MouseEvent<HTMLButtonElement, MouseEvent>,
    camera: types.Camera,
  ) => void;
  date: Dayjs | null;
  setDate: (date: Dayjs | null) => void;
  requestedTimestamp: number | null;
  setRequestedTimestamp: (timestamp: number | null) => void;
  selectedTab: "events" | "timeline";
  setSelectedTab: (tab: "events" | "timeline") => void;
};

export const Layout = memo(
  ({
    cameras,
    selectedCamera,
    selectedRecording,
    setSelectedRecording,
    changeSelectedCamera,
    date,
    setDate,
    requestedTimestamp,
    setRequestedTimestamp,
    selectedTab,
    setSelectedTab,
  }: LayoutProps) => {
    const parentRef = useRef<HTMLDivElement | null>(null);
    const hlsRef = useRef<Hls | null>(null);
    return (
      <Container style={{ display: "flex" }}>
        <div
          style={{
            width: "100%",
            display: "flex",
            flexDirection: "column",
            marginRight: "10px",
          }}
        >
          <PlayerCard
            camera={selectedCamera}
            eventSource={selectedRecording ? selectedRecording.hls_url : null}
            requestedTimestamp={requestedTimestamp}
            selectedTab={selectedTab}
            hlsRef={hlsRef}
          />
          <EventsCameraGrid
            cameras={cameras}
            changeSelectedCamera={changeSelectedCamera}
            selectedCamera={selectedCamera}
          ></EventsCameraGrid>
        </div>
        <Card
          ref={parentRef}
          variant="outlined"
          sx={(theme) => ({
            width: "650px",
            height: `calc(98dvh - ${theme.headerHeight}px)`,
            overflow: "auto",
            overflowX: "hidden",
          })}
        >
          <CardContent sx={{ padding: 0 }}>
            <Tabs
              parentRef={parentRef}
              hlsRef={hlsRef}
              date={date}
              selectedTab={selectedTab}
              setSelectedTab={setSelectedTab}
              selectedCamera={selectedCamera}
              selectedRecording={selectedRecording}
              setSelectedRecording={setSelectedRecording}
              setRequestedTimestamp={setRequestedTimestamp}
            />
          </CardContent>
        </Card>
        <Filters
          cameras={cameras}
          selectedCamera={selectedCamera}
          date={date}
          setDate={setDate}
          changeSelectedCamera={changeSelectedCamera}
        />
      </Container>
    );
  },
);

export const LayoutSmall = memo(
  ({
    cameras,
    selectedCamera,
    selectedRecording,
    setSelectedRecording,
    changeSelectedCamera,
    date,
    setDate,
    requestedTimestamp,
    setRequestedTimestamp,
    selectedTab,
    setSelectedTab,
  }: LayoutProps) => {
    const theme = useTheme();
    const parentRef = useRef<HTMLDivElement | null>(null);
    const hlsRef = useRef<Hls | null>(null);

    // Observe div height to calculate the height of the EventTable
    const [height, setHeight] = useState();
    const observedDiv: any = useRef<HTMLDivElement>();
    const resizeObserver = useRef<ResizeObserver>();
    useEffect(() => {
      if (observedDiv.current) {
        resizeObserver.current = new ResizeObserver(() => {
          setHeight(observedDiv.current.clientHeight + theme.headerHeight);
        });
        resizeObserver.current.observe(observedDiv.current);
      }
      return () => {
        if (resizeObserver.current) {
          resizeObserver.current.disconnect();
        }
      };
    }, [theme.headerHeight]);

    return (
      <Container maxWidth={false} sx={{ height: "100%" }}>
        <div ref={observedDiv}>
          <PlayerCard
            camera={selectedCamera}
            eventSource={selectedRecording ? selectedRecording.hls_url : null}
            requestedTimestamp={requestedTimestamp}
            selectedTab={selectedTab}
            hlsRef={hlsRef}
          />
        </div>
        <Card
          ref={parentRef}
          variant="outlined"
          sx={{
            width: "100%",
            overflow: "auto",
            height: `calc(97dvh - ${height}px)`,
          }}
        >
          <CardContent sx={{ padding: 0 }}>
            <Tabs
              parentRef={parentRef}
              hlsRef={hlsRef}
              date={date}
              selectedTab={selectedTab}
              setSelectedTab={setSelectedTab}
              selectedCamera={selectedCamera}
              selectedRecording={selectedRecording}
              setSelectedRecording={setSelectedRecording}
              setRequestedTimestamp={setRequestedTimestamp}
            />
          </CardContent>
        </Card>
        <Filters
          cameras={cameras}
          selectedCamera={selectedCamera}
          date={date}
          setDate={setDate}
          changeSelectedCamera={changeSelectedCamera}
        />
      </Container>
    );
  },
);
