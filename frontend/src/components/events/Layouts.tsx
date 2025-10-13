import TabContext from "@mui/lab/TabContext";
import TabList from "@mui/lab/TabList";
import TabPanel from "@mui/lab/TabPanel";
import Box from "@mui/material/Box";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import Tab from "@mui/material/Tab";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import { Dayjs } from "dayjs";
import { SyntheticEvent, memo, useCallback, useEffect, useRef } from "react";

import { useFilteredCameras } from "components/camera/useCameraStore";
import { FilterMenu } from "components/events/FilterMenu";
import { FloatingMenu } from "components/events/FloatingMenu";
import { PlayerCard } from "components/events/PlayerCard";
import { EventTable } from "components/events/events/EventTable";
import { TimelineTable } from "components/events/timeline/TimelineTable";
import {
  COLUMN_HEIGHT,
  COLUMN_HEIGHT_SMALL,
  playerCardSmMaxHeight,
} from "components/events/utils";
import { useResizeObserver } from "hooks/UseResizeObserver";
import { insertURLParameter } from "lib/helpers";

const setTableHeight = (
  tabListRef: React.RefObject<HTMLDivElement | null>,
  eventsRef: React.RefObject<HTMLDivElement | null>,
  timelineRef: React.RefObject<HTMLDivElement | null>,
  playerCardGridItemRef: React.MutableRefObject<HTMLDivElement | null>,
  theme: any,
  smBreakpoint: boolean,
) => {
  if (
    tabListRef.current &&
    eventsRef.current &&
    timelineRef.current &&
    playerCardGridItemRef.current
  ) {
    if (smBreakpoint) {
      eventsRef.current.style.height = `calc(${COLUMN_HEIGHT} - ${theme.headerHeight}px - ${tabListRef.current.offsetHeight}px)`;
      timelineRef.current.style.height = eventsRef.current.style.height;
    } else {
      eventsRef.current.style.height = `calc(${COLUMN_HEIGHT_SMALL} - ${theme.headerHeight}px - ${tabListRef.current.offsetHeight}px - ${playerCardGridItemRef.current.offsetHeight}px)`;
      timelineRef.current.style.height = eventsRef.current.style.height;
    }
  }
};

const useSetTableHeight = (
  tabListRef: React.RefObject<HTMLDivElement | null>,
  eventsRef: React.RefObject<HTMLDivElement | null>,
  timelineRef: React.RefObject<HTMLDivElement | null>,
  playerCardGridItemRef: React.MutableRefObject<HTMLDivElement | null>,
) => {
  const theme = useTheme();
  const smBreakpoint = useMediaQuery(theme.breakpoints.up("sm"));

  const _setTableHeight = useCallback(() => {
    setTableHeight(
      tabListRef,
      eventsRef,
      timelineRef,
      playerCardGridItemRef,
      theme,
      smBreakpoint,
    );
  }, [
    tabListRef,
    eventsRef,
    timelineRef,
    playerCardGridItemRef,
    theme,
    smBreakpoint,
  ]);

  useResizeObserver(playerCardGridItemRef, _setTableHeight);
  _setTableHeight();
};

const useSetPlayerCardHeight = (
  playerCardGridItemRef: React.MutableRefObject<HTMLDivElement | null>,
) => {
  const theme = useTheme();
  const smBreakpoint = useMediaQuery(theme.breakpoints.up("sm"));

  useEffect(() => {
    const handleResize = () => {
      if (playerCardGridItemRef.current) {
        if (smBreakpoint) {
          playerCardGridItemRef.current.style.height = `calc(${COLUMN_HEIGHT} - ${theme.headerHeight}px)`;
          playerCardGridItemRef.current.style.maxHeight = "unset";
        } else {
          playerCardGridItemRef.current.style.height = "100%";
          playerCardGridItemRef.current.style.maxHeight = `${playerCardSmMaxHeight()}px`;
        }
      }
    };

    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [playerCardGridItemRef, smBreakpoint, theme.headerHeight]);
};

type TabsProps = {
  date: Dayjs | null;
  selectedTab: "events" | "timeline";
  setSelectedTab: (tab: "events" | "timeline") => void;
  playerCardGridItemRef: React.MutableRefObject<HTMLDivElement | null>;
};
const Tabs = ({
  date,
  selectedTab,
  setSelectedTab,
  playerCardGridItemRef,
}: TabsProps) => {
  const filteredCameras = useFilteredCameras();
  const tabListRef = useRef<HTMLDivElement | null>(null);
  const eventsRef = useRef<HTMLDivElement | null>(null);
  const timelineRef = useRef<HTMLDivElement | null>(null);
  useSetTableHeight(tabListRef, eventsRef, timelineRef, playerCardGridItemRef);

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
          boxSizing: "border-box",
        }}
      >
        {Object.keys(filteredCameras).length > 0 ? (
          <EventTable parentRef={eventsRef} date={date} />
        ) : (
          <Typography align="center" sx={{ marginTop: "20px" }}>
            Select at least one camera to load Events
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
          boxSizing: "border-box",
        }}
      >
        {Object.keys(filteredCameras).length > 0 ? (
          <TimelineTable
            // Force re-render when date changes
            key={`${date?.unix().toString()}`}
            parentRef={timelineRef}
            date={date}
          />
        ) : (
          <Typography align="center" sx={{ marginTop: "20px" }}>
            Select at least one camera to load Timeline
          </Typography>
        )}
      </TabPanel>
    </TabContext>
  );
};

type LayoutProps = {
  date: Dayjs | null;
  setDate: (date: Dayjs | null) => void;
  selectedTab: "events" | "timeline";
  setSelectedTab: (tab: "events" | "timeline") => void;
};

export const Layout = memo(
  ({ date, setDate, selectedTab, setSelectedTab }: LayoutProps) => {
    const theme = useTheme();
    const smBreakpoint = useMediaQuery(theme.breakpoints.up("sm"));
    const playerCardGridItemRef = useRef<HTMLDivElement | null>(null);
    useSetPlayerCardHeight(playerCardGridItemRef);

    return (
      <Box>
        <Grid
          container
          direction={"row"}
          rowSpacing={{ xs: 0.5, sm: 0 }}
          columnSpacing={1}
        >
          <Grid
            ref={playerCardGridItemRef}
            display="flex"
            sx={[
              {
                width: "100%",
              },
              smBreakpoint
                ? {
                    height: `calc(${COLUMN_HEIGHT} - ${theme.headerHeight}px)`,
                    maxHeight: "unset",
                  }
                : {
                    height: "100%",
                    maxHeight: `${playerCardSmMaxHeight()}px`,
                  },
            ]}
            size={{
              xs: 12,
              sm: 8,
              md: 8,
              lg: 9,
              xl: 10,
            }}
          >
            <PlayerCard />
          </Grid>
          <Grid
            size={{
              xs: 12,
              sm: 4,
              md: 4,
              lg: 3,
              xl: 2,
            }}
          >
            <Paper variant="outlined">
              <Tabs
                date={date}
                selectedTab={selectedTab}
                setSelectedTab={setSelectedTab}
                playerCardGridItemRef={playerCardGridItemRef}
              />
            </Paper>
          </Grid>
          <FloatingMenu date={date} setDate={setDate} />
        </Grid>
      </Box>
    );
  },
);
