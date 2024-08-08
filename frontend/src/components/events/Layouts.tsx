import TabContext from "@mui/lab/TabContext";
import TabList from "@mui/lab/TabList";
import TabPanel from "@mui/lab/TabPanel";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Grid from "@mui/material/Grid";
import Tab from "@mui/material/Tab";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import { Dayjs } from "dayjs";
import Hls from "hls.js";
import { SyntheticEvent, memo, useEffect, useRef } from "react";

import { PlayerCard } from "components/events/EventPlayerCard";
import { EventTable } from "components/events/EventTable";
import { FilterMenu } from "components/events/FilterMenu";
import { FloatingMenu } from "components/events/FloatingMenu";
import { TimelineTable } from "components/events/timeline/TimelineTable";
import { COLUMN_HEIGHT, COLUMN_HEIGHT_SMALL } from "components/events/utils";
import { insertURLParameter } from "lib/helpers";
import * as types from "lib/types";

const useSetTableHeight = (
  cardRef: React.RefObject<HTMLDivElement>,
  tabListRef: React.RefObject<HTMLDivElement>,
  eventsRef: React.RefObject<HTMLDivElement>,
  timelineRef: React.RefObject<HTMLDivElement>,
) => {
  const resizeObserver = useRef<ResizeObserver>();
  useEffect(() => {
    if (cardRef.current) {
      resizeObserver.current = new ResizeObserver(() => {
        if (
          !cardRef.current ||
          !tabListRef.current ||
          !eventsRef.current ||
          !timelineRef.current
        ) {
          return;
        }
        timelineRef.current.style.height = `calc(${cardRef.current.clientHeight}px - ${tabListRef.current.clientHeight}px)`;
        eventsRef.current.style.height = timelineRef.current.style.height;
      });
      resizeObserver.current.observe(cardRef.current);
    }
    return () => {
      if (resizeObserver.current) {
        resizeObserver.current.disconnect();
      }
    };
  }, [cardRef, eventsRef, tabListRef, timelineRef]);
};

const useSetCardHeight = (
  gridRef: React.RefObject<HTMLDivElement>,
  cardRef: React.RefObject<HTMLDivElement>,
  playerCardRef: React.RefObject<HTMLDivElement>,
  smBreakpoint: boolean,
) => {
  const theme = useTheme();
  const resizeObserver = useRef<ResizeObserver>();
  useEffect(() => {
    if (playerCardRef.current) {
      resizeObserver.current = new ResizeObserver(() => {
        if (
          !smBreakpoint &&
          cardRef.current &&
          playerCardRef.current &&
          gridRef.current
        ) {
          cardRef.current.style.height = `calc(${COLUMN_HEIGHT_SMALL} - ${
            theme.headerHeight
          }px - ${playerCardRef.current!.clientHeight}px)`;
          cardRef.current.style.maxHeight = "unset";
          gridRef.current.style.height = "unset";
          gridRef.current.style.maxHeight = "unset";
        } else if (smBreakpoint && cardRef.current && gridRef.current) {
          cardRef.current.style.height = `calc(${COLUMN_HEIGHT} - ${theme.headerHeight}px)`;
          cardRef.current.style.maxHeight = cardRef.current.style.height;
          gridRef.current.style.height = cardRef.current.style.height;
          gridRef.current.style.maxHeight = cardRef.current.style.maxHeight;
        }
      });
      resizeObserver.current.observe(playerCardRef.current);
    }
    return () => {
      if (resizeObserver.current) {
        resizeObserver.current.disconnect();
      }
    };
  }, [cardRef, gridRef, playerCardRef, smBreakpoint, theme.headerHeight]);
};

type TabsProps = {
  hlsRef: React.MutableRefObject<Hls | null>;
  date: Dayjs | null;
  selectedTab: "events" | "timeline";
  setSelectedTab: (tab: "events" | "timeline") => void;
  selectedCamera: types.Camera | types.FailedCamera | null;
  selectedEvent: types.CameraEvent | null;
  setSelectedEvent: (event: types.CameraEvent) => void;
  setRequestedTimestamp: (timestamp: number | null) => void;
  cardRef: React.RefObject<HTMLDivElement>;
};
const Tabs = ({
  hlsRef,
  date,
  selectedTab,
  setSelectedTab,
  selectedCamera,
  selectedEvent,
  setSelectedEvent,
  setRequestedTimestamp,
  cardRef,
}: TabsProps) => {
  const tabListRef = useRef<HTMLDivElement | null>(null);
  const eventsRef = useRef<HTMLDivElement | null>(null);
  const timelineRef = useRef<HTMLDivElement | null>(null);
  useSetTableHeight(cardRef, tabListRef, eventsRef, timelineRef);

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
      <TabList
        ref={tabListRef}
        onChange={handleTabChange}
        sx={(theme) => ({
          width: "100%",
          borderBottom: 1,
          borderColor: theme.palette.divider,
          display: "flex",
        })}
      >
        <Tab
          label="Events"
          value="events"
          sx={{ padding: 0, maxWidth: "100%", flexGrow: 1 }}
        />
        <Tab
          label="Timeline"
          value="timeline"
          sx={(theme) => ({
            padding: 0,
            maxWidth: "100%",
            flexGrow: 1,
            borderRight: 1,
            borderColor: theme.palette.divider,
          })}
        />
        <FilterMenu />
      </TabList>
      <TabPanel
        ref={eventsRef}
        value="events"
        sx={{
          padding: 0,
          paddingTop: "5px",
          overflow: "auto",
          overflowX: "hidden",
        }}
      >
        {selectedCamera ? (
          <EventTable
            parentRef={eventsRef}
            camera={selectedCamera}
            date={date}
            selectedEvent={selectedEvent}
            setSelectedEvent={setSelectedEvent}
            setRequestedTimestamp={setRequestedTimestamp}
          />
        ) : (
          <Typography align="center" sx={{ marginTop: "20px" }}>
            Select a camera to load Events
          </Typography>
        )}
      </TabPanel>
      <TabPanel
        ref={timelineRef}
        value="timeline"
        sx={{
          padding: 0,
          paddingTop: "5px",
          paddingBottom: "50px",
          overflow: "auto",
          overflowX: "hidden",
        }}
      >
        {selectedCamera ? (
          <TimelineTable
            // Force re-render when camera or date changes
            key={`${selectedCamera.identifier}-${date?.unix().toString()}`}
            parentRef={timelineRef}
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
  cameras: types.CamerasOrFailedCameras;
  selectedCamera: types.Camera | types.FailedCamera | null;
  selectedEvent: types.CameraEvent | null;
  setSelectedEvent: (event: types.CameraEvent) => void;
  changeSelectedCamera: (
    ev: React.MouseEvent<HTMLButtonElement, MouseEvent>,
    camera: types.Camera | types.FailedCamera,
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
    selectedEvent,
    setSelectedEvent,
    changeSelectedCamera,
    date,
    setDate,
    requestedTimestamp,
    setRequestedTimestamp,
    selectedTab,
    setSelectedTab,
  }: LayoutProps) => {
    const theme = useTheme();
    const smBreakpoint = useMediaQuery(theme.breakpoints.up("sm"));
    const hlsRef = useRef<Hls | null>(null);
    const cardRef = useRef<HTMLDivElement | null>(null);
    const playerCardRef = useRef<HTMLDivElement | null>(null);
    const gridRef = useRef<HTMLDivElement | null>(null);
    useSetCardHeight(gridRef, cardRef, playerCardRef, smBreakpoint);

    return (
      <Box>
        <Grid
          container
          direction={"row"}
          rowSpacing={{ xs: 0.5, sm: 0 }}
          columnSpacing={1}
        >
          <Grid ref={gridRef} item xs={12} sm={8} display="flex">
            <PlayerCard
              camera={selectedCamera}
              selectedEvent={selectedEvent}
              requestedTimestamp={requestedTimestamp}
              selectedTab={selectedTab}
              hlsRef={hlsRef}
              playerCardRef={playerCardRef}
            />
          </Grid>
          <Grid item xs={12} sm={4}>
            <Card ref={cardRef} variant="outlined">
              <CardContent sx={{ padding: 0 }}>
                <Tabs
                  hlsRef={hlsRef}
                  date={date}
                  selectedTab={selectedTab}
                  setSelectedTab={setSelectedTab}
                  selectedCamera={selectedCamera}
                  selectedEvent={selectedEvent}
                  setSelectedEvent={setSelectedEvent}
                  setRequestedTimestamp={setRequestedTimestamp}
                  cardRef={cardRef}
                />
              </CardContent>
            </Card>
          </Grid>
          <FloatingMenu
            cameras={cameras}
            selectedCamera={selectedCamera}
            date={date}
            setDate={setDate}
            changeSelectedCamera={changeSelectedCamera}
          />
        </Grid>
      </Box>
    );
  },
);
