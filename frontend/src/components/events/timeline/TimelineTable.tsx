import Box from "@mui/material/Box";
import dayjs from "dayjs";
import { memo, useEffect, useRef, useState } from "react";

import { ActivityLine } from "components/events/timeline/ActivityLine";
import { HoverLine } from "components/events/timeline/HoverLine";
import { ObjectEvent } from "components/events/timeline/ObjectEvent";
import { Spacer } from "components/events/timeline/Spacer";
import { TimeTick } from "components/events/timeline/TimeTick";
import { Loading } from "components/loading/Loading";
import queryClient from "lib/api/client";
import { useEvents } from "lib/api/events";
import { dateToTimestamp } from "lib/helpers";
import * as types from "lib/types";

export const TICK_HEIGHT = 8;
export const SCALE = 60;
export const EXTRA_TICKS = 10;

const round = (num: number) => Math.ceil(num / SCALE) * SCALE;

const activityLine = (
  start: number,
  cameraEvent: types.CameraMotionEvent | types.CameraRecordingEvent,
  lines: JSX.Element[],
  timeTicks: number[],
) => {
  const indexStart = Math.round((start - cameraEvent.end_timestamp) / SCALE);
  const indexEnd = Math.round((start - cameraEvent.start_timestamp) / SCALE);
  if (cameraEvent.end_timestamp - cameraEvent.start_timestamp <= SCALE) {
    lines[indexStart] = (
      <ActivityLine
        key={`line-${timeTicks[indexStart]}`}
        active={true}
        cameraEvent={cameraEvent}
        variant="round"
      />
    );
    return;
  }
  lines[indexStart] = (
    <ActivityLine
      key={`line-${timeTicks[indexStart]}`}
      active={true}
      cameraEvent={cameraEvent}
      variant="first"
    />
  );
  lines[indexEnd] = (
    <ActivityLine
      key={`line-${timeTicks[indexEnd]}`}
      active={true}
      cameraEvent={cameraEvent}
      variant="last"
    />
  );
  for (let i = indexStart + 1; i < indexEnd; i++) {
    lines[i] = (
      <ActivityLine
        key={`line-${timeTicks[i]}`}
        active={true}
        cameraEvent={cameraEvent}
        variant="middle"
      />
    );
  }
};

const objectEvent = (
  start: number,
  cameraEvent: types.CameraObjectEvent,
  cameraEventIndex: number,
  events: JSX.Element[],
  timeTicks: number[],
) => {
  const index = Math.round((start - cameraEvent.timestamp) / SCALE);
  events[index] = (
    <ObjectEvent
      key={`object-${timeTicks[index]}-${cameraEventIndex}`}
      objectEvent={cameraEvent}
      eventIndex={cameraEventIndex}
    />
  );
};

// Generate initial timeline with no event data
const useInitialTimeline = (
  startRef: React.MutableRefObject<number>,
  end: number,
  setTimeTicks: React.Dispatch<React.SetStateAction<number[]>>,
  setRows: React.Dispatch<React.SetStateAction<JSX.Element[]>>,
  setLines: React.Dispatch<React.SetStateAction<JSX.Element[]>>,
  setEvents: React.Dispatch<React.SetStateAction<JSX.Element[]>>,
) => {
  useEffect(() => {
    let timeTick = startRef.current;
    const _timeTicks: number[] = [];
    const _rows: JSX.Element[] = [];
    const _lines: JSX.Element[] = [];
    const _events: JSX.Element[] = [];
    while (timeTick >= end) {
      _timeTicks.push(timeTick);
      _rows.push(<TimeTick key={`tick-${timeTick}`} time={timeTick} />);
      _lines.push(
        <ActivityLine
          key={`line-${timeTick}`}
          active={false}
          cameraEvent={null}
          variant={null}
        />,
      );
      _events.push(
        <Spacer
          key={`spacer-${timeTick}`}
          time={timeTick}
          height={TICK_HEIGHT}
        />,
      );
      timeTick -= SCALE;
    }
    setTimeTicks(_timeTicks);
    setRows(_rows);
    setLines(_lines);
    setEvents(_events);
    // Should only run once on initial render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
};

// Add timeticks every SCALE seconds
const useAddTicks = (
  startRef: React.MutableRefObject<number>,
  setTimeTicks: React.Dispatch<React.SetStateAction<number[]>>,
  setRows: React.Dispatch<React.SetStateAction<JSX.Element[]>>,
  setLines: React.Dispatch<React.SetStateAction<JSX.Element[]>>,
  setEvents: React.Dispatch<React.SetStateAction<JSX.Element[]>>,
) => {
  const timeout = useRef<NodeJS.Timeout>();

  useEffect(() => {
    const addTicks = (ticksToAdd: number) => {
      let timeTick = startRef.current;
      const _timeTicks: number[] = [];
      const _rows: JSX.Element[] = [];
      const _lines: JSX.Element[] = [];
      const _events: JSX.Element[] = [];

      for (let i = 0; i < ticksToAdd; i++) {
        timeTick += SCALE;
        _timeTicks.push(timeTick);
        _rows.push(<TimeTick key={`tick-${timeTick}`} time={timeTick} />);
        _lines.push(
          <ActivityLine
            key={`line-${timeTick}`}
            active={false}
            cameraEvent={null}
            variant={null}
          />,
        );
        _events.push(
          <Spacer
            key={`spacer-${timeTick}`}
            time={timeTick}
            height={TICK_HEIGHT}
          />,
        );
      }

      startRef.current = timeTick;
      setTimeTicks((prevTimeTicks) => [..._timeTicks, ...prevTimeTicks]);
      setRows((prevRows) => [..._rows, ...prevRows]);
      setLines((prevLines) => [..._lines, ...prevLines]);
      setEvents((prevEvents) => [..._events, ...prevEvents]);
    };

    const recursiveTimeout = () => {
      const timeDiff =
        dayjs().unix() - (startRef.current - SCALE * EXTRA_TICKS);
      if (timeDiff >= SCALE) {
        const ticksToAdd = Math.floor(timeDiff / SCALE);
        addTicks(ticksToAdd);
      }
      timeout.current = setTimeout(recursiveTimeout, SCALE * 1000);
    };
    recursiveTimeout();
    return () => {
      if (timeout.current) {
        clearTimeout(timeout.current);
      }
    };
  }, [setEvents, setLines, setRows, setTimeTicks, startRef]);
};

// Update timeline with event data
const useUpdateTimeline = (
  startRef: React.MutableRefObject<number>,
  eventsData: types.CameraEvent[],
  timeTicks: number[],
  setTimeTicks: React.Dispatch<React.SetStateAction<number[]>>,
  rows: JSX.Element[],
  setRows: React.Dispatch<React.SetStateAction<JSX.Element[]>>,
  lines: JSX.Element[],
  setLines: React.Dispatch<React.SetStateAction<JSX.Element[]>>,
  events: JSX.Element[],
  setEvents: React.Dispatch<React.SetStateAction<JSX.Element[]>>,
) => {
  useEffect(() => {
    if (eventsData.length === 0) {
      return;
    }
    const _timeTicks = [...timeTicks];
    const _rows = [...rows];
    const _lines = [...lines];
    const _events = [...events];

    // Loop over events where type is motion
    eventsData
      .filter(
        (cameraEvent): cameraEvent is types.CameraMotionEvent =>
          cameraEvent.type === "motion",
      )
      .forEach((cameraEvent) => {
        activityLine(startRef.current, cameraEvent, _lines, _timeTicks);
      });
    // Loop over events where type is recording
    eventsData
      .filter(
        (cameraEvent): cameraEvent is types.CameraRecordingEvent =>
          cameraEvent.type === "recording",
      )
      .forEach((cameraEvent) => {
        activityLine(startRef.current, cameraEvent, _lines, _timeTicks);
      });
    // Loop over events where type is object
    eventsData
      .filter(
        (cameraEvent): cameraEvent is types.CameraObjectEvent =>
          cameraEvent.type === "object",
      )
      .forEach((cameraEvent, index) => {
        objectEvent(startRef.current, cameraEvent, index, _events, _timeTicks);
      });

    setTimeTicks(_timeTicks);
    setRows(_rows);
    setLines(_lines);
    setEvents(_events);
    /// Run only when eventsData changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventsData]);
};

type TimelineTableProps = {
  camera: types.Camera;
  setSource: (source: string | null) => void;
};
export const TimelineTable = memo(
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  ({ camera, setSource }: TimelineTableProps) => {
    const firstRenderRef = useRef(true);
    const containerRef = useRef<HTMLDivElement | null>(null);
    const startRef = useRef<number>(
      round(dateToTimestamp(new Date()) + SCALE * EXTRA_TICKS),
    );
    const endRef = useRef<number>(
      dateToTimestamp(new Date(new Date().setHours(0, 0, 0, 0))),
    );
    const [timeTicks, setTimeTicks] = useState<number[]>([]);
    const [rows, setRows] = useState<JSX.Element[]>([]);
    const [lines, setLines] = useState<JSX.Element[]>([]);
    const [events, setEvents] = useState<JSX.Element[]>([]);
    const eventsQuery = useEvents({
      camera_identifier: camera.identifier,
      time_from: endRef.current,
      time_to: startRef.current,
      configOptions: {
        notifyOnChangeProps: ["data"],
      },
    });
    const eventsData = eventsQuery.data?.events || [];

    // Generate initial timeline with no event data
    useInitialTimeline(
      startRef,
      endRef.current,
      setTimeTicks,
      setRows,
      setLines,
      setEvents,
    );
    // Add timeticks every SCALE seconds
    useAddTicks(startRef, setTimeTicks, setRows, setLines, setEvents);
    // Update timeline with event data
    useUpdateTimeline(
      startRef,
      eventsData,
      timeTicks,
      setTimeTicks,
      rows,
      setRows,
      lines,
      setLines,
      events,
      setEvents,
    );

    if (eventsQuery.isLoading && firstRenderRef.current) {
      return <Loading text="Loading Timeline" fullScreen={false} />;
    }
    firstRenderRef.current = false;

    return (
      <Box
        ref={containerRef}
        style={{ display: "flex" }}
        onClick={() => queryClient.invalidateQueries(["events"])}
      >
        <HoverLine
          containerRef={containerRef}
          startRef={startRef}
          endRef={endRef}
        />
        <Box>{rows}</Box>
        <Box>{lines}</Box>
        <Box sx={{ width: "100%" }}>{events}</Box>
      </Box>
    );
  },
);
