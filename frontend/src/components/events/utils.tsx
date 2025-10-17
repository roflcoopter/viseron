import AirIcon from "@mui/icons-material/Air";
import DirectionsCarIcon from "@mui/icons-material/DirectionsCar";
import PersonIcon from "@mui/icons-material/DirectionsWalk";
import FaceIcon from "@mui/icons-material/Face";
import ImageSearchIcon from "@mui/icons-material/ImageSearch";
import PetsIcon from "@mui/icons-material/Pets";
import VideoFileIcon from "@mui/icons-material/VideoFile";
import dayjs, { Dayjs } from "dayjs";
import Hls, { Fragment } from "hls.js";
import { useCallback } from "react";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import { useShallow } from "zustand/react/shallow";

import { useCameraStore } from "components/camera/useCameraStore";
import LicensePlateRecognitionIcon from "components/icons/LicensePlateRecognition";
import { useCameras } from "lib/api/cameras";
import { useSubscribeTimespans } from "lib/commands";
import { BLANK_IMAGE, dateToTimestamp } from "lib/helpers";
import * as types from "lib/types";

export const TICK_HEIGHT = 8;
export const SCALE = 60;
export const EXTRA_TICKS = 10;
export const COLUMN_HEIGHT = "99dvh";
export const COLUMN_HEIGHT_SMALL = "98.5dvh";
export const EVENT_ICON_HEIGHT = 30;
export const LIVE_EDGE_DELAY = 10;

export const playerCardSmMaxHeight = () => window.innerHeight * 0.4;

// Get all possible keys from Filters
export type FilterKeysFromFilters =
  | keyof Filters["eventTypes"]
  | keyof Pick<Filters, Exclude<keyof Filters, "eventTypes">>;

// Update FilterKey to use the mapped type
type FilterKey = FilterKeysFromFilters;

export type Filters = {
  eventTypes: {
    [key in types.CameraEvent["type"]]: {
      label: string;
      checked: boolean;
    };
  };
  groupCameras: { label: string; checked: boolean };
  lookbackAdjust: { label: string; checked: boolean };
};

const initialFilters: Filters = {
  eventTypes: {
    motion: { label: "Motion", checked: true },
    object: { label: "Object", checked: true },
    recording: { label: "Recording", checked: true },
    face_recognition: { label: "Face Recognition", checked: true },
    license_plate_recognition: {
      label: "License Plate Recognition",
      checked: true,
    },
  },
  groupCameras: { label: "Group Cameras", checked: false },
  lookbackAdjust: { label: "Adjust for Lookback", checked: true },
};

interface FilterState {
  filters: Filters;
  setFilters: (filters: Filters) => void;
  toggleFilter: (filterKey: FilterKey) => void;
}

export const useFilterStore = create<FilterState>()(
  persist(
    (set) => ({
      filters: initialFilters,
      setFilters: (filters) => set({ filters }),
      toggleFilter: (filterKey) => {
        set((state) => {
          const newFilters = { ...state.filters };

          switch (filterKey) {
            case "groupCameras":
            case "lookbackAdjust":
              newFilters[filterKey] = {
                ...newFilters[filterKey],
                checked: !newFilters[filterKey].checked,
              };
              break;
            case "motion":
            case "object":
            case "recording":
            case "face_recognition":
            case "license_plate_recognition":
              newFilters.eventTypes[filterKey] = {
                ...newFilters.eventTypes[filterKey],
                checked: !newFilters.eventTypes[filterKey].checked,
              };
              break;
            default:
              // eslint-disable-next-line no-case-declarations
              const _exhaustiveCheck: never = filterKey;
              throw new Error(`Unhandled filter key: ${_exhaustiveCheck}`);
          }

          return { filters: newFilters };
        });
      },
    }),
    { name: "filter-store", version: 2 },
  ),
);

interface EventState {
  selectedEvent: types.CameraEvent | null;
  setSelectedEvent: (event: types.CameraEvent | null) => void;
}

export const useEventStore = create<EventState>((set) => ({
  selectedEvent: null,
  setSelectedEvent: (event) => set({ selectedEvent: event }),
}));

interface AvailableTimespansState {
  availableTimespans: types.HlsAvailableTimespan[];
  setAvailableTimespans: (timespans: types.HlsAvailableTimespan[]) => void;
  availableTimespansRef: React.MutableRefObject<types.HlsAvailableTimespan[]>;
}

export const useAvailableTimespansStore = create<AvailableTimespansState>(
  (set) => ({
    availableTimespans: [],
    setAvailableTimespans: (timespans) =>
      set((state) => {
        state.availableTimespansRef.current = timespans;
        return { ...state, availableTimespans: timespans };
      }),
    availableTimespansRef: { current: [] },
  }),
);

interface HlsStore {
  hlsRefs: React.MutableRefObject<Hls | null>[];
  addHlsRef: (hlsRef: React.MutableRefObject<Hls | null>) => void;
  removeHlsRef: (hlsRef: React.MutableRefObject<Hls | null>) => void;
  hlsRefsError: Map<React.MutableRefObject<Hls | null>, string | null>;
  setHlsRefsError: (
    hlsRef: React.MutableRefObject<Hls | null>,
    error: string | null,
  ) => void;
}

export const useHlsStore = create<HlsStore>((set) => ({
  hlsRefs: [],
  // add a new Hls ref to the store only if it does not exist
  addHlsRef: (hlsRef: React.MutableRefObject<Hls | null>) =>
    set((state) => {
      if (state.hlsRefs.includes(hlsRef)) {
        return state;
      }
      return {
        ...state,
        hlsRefs: [...state.hlsRefs, hlsRef],
      };
    }),
  removeHlsRef: (hlsRef: React.MutableRefObject<Hls | null>) =>
    set((state) => ({
      ...state,
      hlsRefs: state.hlsRefs.filter((ref) => ref !== hlsRef),
    })),
  hlsRefsError: new Map(),
  setHlsRefsError: (hlsRef, error) =>
    set((state) => {
      if (state.hlsRefsError.get(hlsRef) === error) {
        return state;
      }
      return {
        ...state,
        hlsRefsError: new Map(state.hlsRefsError.set(hlsRef, error)),
      };
    }),
}));

interface ReferencePlayerStore {
  referencePlayer: Hls | null;
  setReferencePlayer: (player: Hls | null) => void;
  isPlaying: boolean;
  setIsPlaying: (playing: boolean) => void;
  isLive: boolean;
  setIsLive: (live: boolean) => void;
  isMuted: boolean;
  setIsMuted: (muted: boolean) => void;
  playbackSpeed: number;
  setPlaybackSpeed: (speed: number) => void;
  requestedTimestamp: number;
  setRequestedTimestamp: (timestamp: number) => void;
  playingDateRef: React.MutableRefObject<number>;
}

export const useReferencePlayerStore = create<ReferencePlayerStore>((set) => ({
  referencePlayer: null,
  setReferencePlayer: (referencePlayer) => set({ referencePlayer }),
  isPlaying: true,
  setIsPlaying: (isPlaying) => set({ isPlaying }),
  isLive: true,
  setIsLive: (isLive) => set({ isLive }),
  isMuted: true,
  setIsMuted: (isMuted) => set({ isMuted }),
  playbackSpeed: 1,
  setPlaybackSpeed: (playbackSpeed) => set({ playbackSpeed }),
  requestedTimestamp: dayjs().unix() - LIVE_EDGE_DELAY,
  setRequestedTimestamp: (requestedTimestamp) =>
    set((state) => {
      state.playingDateRef.current = requestedTimestamp;
      return { ...state, requestedTimestamp };
    }),
  playingDateRef: { current: dayjs().unix() - LIVE_EDGE_DELAY },
}));

export const DEFAULT_ITEM: TimelineItem = {
  time: 0,
  timedEvent: null,
  snapshotEvents: null,
  availableTimespan: false,
  activityLineVariant: null,
};

export type TimelineItem = {
  time: number;
  timedEvent: null | types.CameraMotionEvent | types.CameraRecordingEvent;
  snapshotEvents: null | types.CameraSnapshotEvents;
  availableTimespan: boolean;
  activityLineVariant: "first" | "middle" | "last" | "round" | null;
};

export type TimelineItems = {
  [key: string]: TimelineItem;
};

// Get a Date object that corresponds to 'position'
export const getDateAtPosition = (
  position: number,
  height: number,
  startRef: React.MutableRefObject<number>,
  endRef: React.MutableRefObject<number>,
) => {
  // Calculate the percentage of cursor position within the container
  const percentage = position / height;

  // First time tick is preceded by a margin of half the time tick height
  // so we add half the scale to get the correct time
  const _start = startRef.current * 1000 + (SCALE * 1000) / 2;
  // Last time tick is followed by a margin of half the time tick height
  // so we subtract half the scale to get the correct time
  const _end = endRef.current * 1000 - (SCALE * 1000) / 2;
  // Calculate the time difference in milliseconds between start and end dates
  const timeDifference = _end - _start;

  // Calculate the time corresponding to the cursor position
  const dateAtCursor = new Date(_start + percentage * timeDifference);
  return dateAtCursor;
};

// Calculate the Y-position on the timeline of the requested timestamp
export const getYPosition = (
  startTimestamp: number,
  endTimestamp: number,
  requestedTimestamp: number,
  timelineHeight: number,
): number => {
  // Calculate the start and end timestamps with a margin of half the SCALE
  const _start = startTimestamp + SCALE / 2;
  const _end = endTimestamp - SCALE / 2;
  // Calculate the total time duration from start to end
  const totalTime = _end - _start;
  // Calculate the time elapsed from start to the requested timestamp
  const elapsedTime = requestedTimestamp - _start;
  // Calculate the proportion of time elapsed relative to the total time
  const timeProportion = elapsedTime / totalTime;
  // Calculate the Y-position of the requested timestamp
  const yPosition = timeProportion * timelineHeight;
  return yPosition;
};

// Round to neareset SCALE
export const round = (num: number) => Math.ceil(num / SCALE) * SCALE;

// Calculate the start time of the timeline, called on first render
export const calculateStart = (date: Dayjs | null) => {
  if (!date) {
    return round(dateToTimestamp(new Date()) + SCALE * EXTRA_TICKS);
  }
  // if date is today, start at current time
  if (date.isSame(dayjs(), "day")) {
    return round(dateToTimestamp(new Date()) + SCALE * EXTRA_TICKS);
  }
  // Otherwise start at midnight the next day
  return dateToTimestamp(
    new Date(date.add(1, "day").toDate().setHours(0, 0, 0, 0)),
  );
};

// Calculate the end time of the timeline, called on first render
export const calculateEnd = (date: Dayjs | null) =>
  dateToTimestamp(
    date
      ? new Date(date.toDate().setHours(0, 0, 0, 0))
      : new Date(new Date().setHours(0, 0, 0, 0)),
  );

// Calculate the number of items to render in the virtual list
export const calculateItemCount = (
  startRef: React.MutableRefObject<number>,
  endRef: React.MutableRefObject<number>,
) => (startRef.current - endRef.current) / SCALE + 1;

// Calculate the time from the index
export const calculateTimeFromIndex = (
  startRef: React.MutableRefObject<number>,
  index: number,
) => startRef.current - index * SCALE;

// Calculate the index from the time
export const calculateIndexFromTime = (
  startRef: React.MutableRefObject<number>,
  timestamp: number | null,
) => Math.round((startRef.current - (timestamp || dayjs().unix())) / SCALE);

// Common logic for items that affect the activity line
export function createActivityLineItem(
  startRef: React.MutableRefObject<number>,
  indexStart: number,
  indexEnd: number,
  event: boolean,
  eventType: "availableTimespan",
): TimelineItems;
export function createActivityLineItem(
  startRef: React.MutableRefObject<number>,
  indexStart: number,
  indexEnd: number,
  event: types.CameraTimedEvents,
  eventType: "timedEvent",
): TimelineItems;
export function createActivityLineItem(
  startRef: React.MutableRefObject<number>,
  indexStart: number,
  indexEnd: number,
  event: types.CameraEvent | boolean,
  eventType: "availableTimespan" | "timedEvent",
): TimelineItems {
  const timelineItems: TimelineItems = {};

  let time = calculateTimeFromIndex(startRef, indexStart);
  timelineItems[time] = {
    ...DEFAULT_ITEM,
    time,
    [eventType]: event,
    activityLineVariant: indexStart === indexEnd ? "round" : "first",
  };

  if (indexStart !== indexEnd) {
    time = calculateTimeFromIndex(startRef, indexEnd);
    timelineItems[time] = {
      ...DEFAULT_ITEM,
      time,
      [eventType]: event,
      activityLineVariant: "last",
    };

    for (let i = indexStart + 1; i < indexEnd; i++) {
      time = calculateTimeFromIndex(startRef, i);
      timelineItems[time] = {
        ...DEFAULT_ITEM,
        time,
        [eventType]: event,
        activityLineVariant: "middle",
      };
    }
  }

  return timelineItems;
}

// For snapshot events, make sure adjacent events are grouped together
const addSnapshotEvent = (
  startRef: React.MutableRefObject<number>,
  timelineItems: TimelineItems,
  cameraEvent: types.CameraSnapshotEvent,
) => {
  // Find number of grouped ticks
  const groupedTicks = Math.ceil(EVENT_ICON_HEIGHT / TICK_HEIGHT);

  // Check if previous ticks have snapshot events and group them
  const index = calculateIndexFromTime(startRef, cameraEvent.timestamp);
  const groupedSnapshotEvents: types.CameraSnapshotEvents = [];
  for (let i = 0; i < groupedTicks; i++) {
    const time = calculateTimeFromIndex(startRef, index - i);
    if (time in timelineItems && timelineItems[time].snapshotEvents) {
      groupedSnapshotEvents.push(
        ...(timelineItems[time]?.snapshotEvents || []),
      );
      timelineItems[time].snapshotEvents = null;
    }
  }

  // Add the (grouped) snapshot events to the timeline
  const time = calculateTimeFromIndex(startRef, index);
  timelineItems[time] = {
    ...DEFAULT_ITEM,
    ...timelineItems[time],
    time,
    snapshotEvents: [
      ...groupedSnapshotEvents,
      ...(timelineItems[time]?.snapshotEvents || []),
      cameraEvent,
    ],
  };
};

// Get the timeline items from the events and available timespans
export const getTimelineItems = (
  startRef: React.MutableRefObject<number>,
  eventsData: types.CameraEvent[],
  availableTimespansData: types.HlsAvailableTimespan[],
  filters: Filters,
) => {
  let timelineItems: TimelineItems = {};

  const filteredEvents = eventsData.filter(
    (event) => filters.eventTypes[event.type].checked,
  );

  // Loop over available HLS files
  availableTimespansData.forEach((timespan) => {
    const indexEnd = calculateIndexFromTime(startRef, timespan.start);
    const indexStart = calculateIndexFromTime(startRef, timespan.end);

    timelineItems = {
      ...timelineItems,
      ...createActivityLineItem(
        startRef,
        indexStart,
        indexEnd,
        true,
        "availableTimespan",
      ),
    };
  });

  // Loop over events where type is motion or recording
  filteredEvents
    .filter(
      (cameraEvent): cameraEvent is types.CameraTimedEvents =>
        cameraEvent.type === "motion" || cameraEvent.type === "recording",
    )
    // Create a copy of the array and sort it by type
    .slice()
    .sort((cameraEvent, _) => (cameraEvent.type === "recording" ? 1 : -1))
    .forEach((cameraEvent) => {
      const indexEnd = calculateIndexFromTime(
        startRef,
        cameraEvent.start_timestamp,
      );
      const indexStart = calculateIndexFromTime(
        startRef,
        cameraEvent.end_timestamp,
      );

      timelineItems = {
        ...timelineItems,
        ...createActivityLineItem(
          startRef,
          indexStart,
          indexEnd,
          cameraEvent,
          "timedEvent",
        ),
      };
    });

  filteredEvents
    .filter(
      (
        cameraEvent,
      ): cameraEvent is
        | types.CameraObjectEvent
        | types.CameraFaceRecognitionEvent
        | types.CameraLicensePlateRecognitionEvent =>
        cameraEvent.type === "object" ||
        cameraEvent.type === "face_recognition" ||
        cameraEvent.type === "license_plate_recognition",
    )
    .forEach((cameraEvent) => {
      addSnapshotEvent(startRef, timelineItems, cameraEvent);
    });
  return timelineItems;
};

// Get timeline items for the virtual list
export const getItem = (time: number, items: TimelineItems) =>
  time.toString() in items ? items[time] : { ...DEFAULT_ITEM, time };

// Convert confidence to percentage
export const convertToPercentage = (confidence: number) =>
  Math.round(confidence * 100);

// Get HLS fragment by timestamp
export const findFragmentByTimestamp = (
  fragments: Fragment[],
  timestampMillis: number,
): Fragment | null => {
  for (const fragment of fragments) {
    if (fragment.programDateTime) {
      const fragmentStart = fragment.programDateTime;
      const fragmentEnd = fragment.programDateTime + fragment.duration * 1000;
      if (timestampMillis >= fragmentStart && timestampMillis <= fragmentEnd) {
        return fragment;
      }
    }
  }

  return null; // Return null if no matching fragment is found
};

// Find the closest fragment that is newer than the timestamp
export const findClosestFragment = (
  fragments: Fragment[],
  timestampMillis: number,
): Fragment | null => {
  let closestFragment = null;
  let closestFragmentTime = Infinity;

  for (const fragment of fragments) {
    if (fragment.programDateTime) {
      const fragmentStart = fragment.programDateTime;
      if (
        fragmentStart >= timestampMillis &&
        fragmentStart < closestFragmentTime
      ) {
        closestFragment = fragment;
        closestFragmentTime = fragmentStart;
      }
    }
  }

  return closestFragment;
};

// Calculate the seek target for the requested timestamp
export const getSeekTarget = (
  fragment: Fragment,
  timestampMillis: number,
): number => {
  let seekTarget = fragment.start;
  if (timestampMillis > fragment.programDateTime!) {
    seekTarget =
      fragment.start + (timestampMillis - fragment.programDateTime!) / 1000;
  } else {
    seekTarget = fragment.start;
  }
  return seekTarget;
};

// Calculate the height of the camera while maintaining aspect ratio
export const calculateHeight = (
  cameraWidth: number,
  cameraHeight: number,
  width: number,
): number => (width * cameraHeight) / cameraWidth;

export const calculateWidth = (
  cameraWidth: number,
  cameraHeight: number,
  height: number,
): number => (height * cameraWidth) / cameraHeight;

export const getSrc = (event: types.CameraEvent) => {
  switch (event.type) {
    case "recording":
      return event.thumbnail_path;
    case "object":
    case "face_recognition":
    case "license_plate_recognition":
    case "motion":
      return event.snapshot_path || BLANK_IMAGE;
    default:
      return event satisfies never;
  }
};

// Extract unique snapshot event types into a map
export const extractUniqueTypes = (snapshotEvents: types.CameraEvent[]) => {
  if (!snapshotEvents) {
    return {};
  }

  const typeMap = new Map<string, types.CameraEvent[]>();

  snapshotEvents.forEach((event) => {
    const type = event.type;
    if (!typeMap.has(type)) {
      typeMap.set(type, []);
    }
    typeMap.get(type)!.unshift(event);
  });

  const result: { [key: string]: types.CameraEvent[] } = {};
  typeMap.forEach((value, key) => {
    result[key] = value;
  });

  return result;
};

// Extract unique labels for object snapshot events into a map
export const extractUniqueLabels = (objectEvents: types.CameraObjectEvents) => {
  if (!objectEvents) {
    return {};
  }

  const labelMap = new Map<string, types.CameraObjectEvents>();

  objectEvents.forEach((event) => {
    let label;
    switch (event.label) {
      case "car":
      case "truck":
      case "vehicle":
        label = "vehicle";
        break;
      default:
        label = event.label;
    }

    if (!labelMap.has(label)) {
      labelMap.set(label, []);
    }
    labelMap.get(label)!.push(event);
  });

  const result: { [key: string]: types.CameraObjectEvents } = {};
  labelMap.forEach((value, key) => {
    result[key] = value;
  });

  return result;
};

export const getEventTime = (event: types.CameraEvent): string => {
  switch (event.type) {
    case "license_plate_recognition":
    case "face_recognition":
    case "object":
      return event.time;
    case "motion":
    case "recording":
      return event.start_time;
    default:
      return event satisfies never;
  }
};

export const getEventTimestamp = (event: types.CameraEvent): number => {
  switch (event.type) {
    case "license_plate_recognition":
    case "face_recognition":
    case "object":
      return event.timestamp;
    case "motion":
    case "recording":
      return event.start_timestamp;
    default:
      return event satisfies never;
  }
};

const isTimespanAvailable = (
  timestamp: number,
  availableTimespans: types.HlsAvailableTimespan[],
) => {
  for (const timespan of availableTimespans) {
    if (timestamp >= timespan.start - 5 && timestamp <= timespan.end + 5) {
      return true;
    }
  }
  return false;
};

export const useSelectEvent = () => {
  const { setSelectedEvent } = useEventStore(
    useShallow((state) => ({
      setSelectedEvent: state.setSelectedEvent,
    })),
  );
  const { setRequestedTimestamp } = useReferencePlayerStore(
    useShallow((state) => ({
      setRequestedTimestamp: state.setRequestedTimestamp,
    })),
  );
  const { availableTimespansRef } = useAvailableTimespansStore(
    useShallow((state) => ({
      availableTimespansRef: state.availableTimespansRef,
    })),
  );
  const { lookbackAdjust } = useFilterStore(
    useShallow((state) => ({
      lookbackAdjust: state.filters.lookbackAdjust.checked,
    })),
  );

  const selectEvent = useCallback(
    (event: types.CameraEvent) => {
      const eventTimestamp = Math.round(getEventTimestamp(event));
      if (isTimespanAvailable(eventTimestamp, availableTimespansRef.current)) {
        setSelectedEvent(event);
        setRequestedTimestamp(
          eventTimestamp - (lookbackAdjust ? event.lookback : 0),
        );
        return;
      }

      setSelectedEvent(event);
      setRequestedTimestamp(0);
    },
    [
      availableTimespansRef,
      setSelectedEvent,
      setRequestedTimestamp,
      lookbackAdjust,
    ],
  );
  return selectEvent;
};

const labelToIcon = (label: string) => {
  switch (label) {
    case "person":
      return PersonIcon;

    case "car":
    case "truck":
    case "vehicle":
      return DirectionsCarIcon;

    case "dog":
    case "cat":
    case "animal":
      return PetsIcon;

    default:
      return ImageSearchIcon;
  }
};

const iconMap = {
  object: PersonIcon,
  face_recognition: FaceIcon,
  license_plate_recognition: LicensePlateRecognitionIcon,
  motion: AirIcon,
  recording: VideoFileIcon,
};

export const getIcon = (event: types.CameraEvent) => {
  switch (event.type) {
    case "object":
      return labelToIcon(event.label);
    case "face_recognition":
    case "license_plate_recognition":
    case "motion":
    case "recording":
      return iconMap[event.type];
    default:
      return event satisfies never;
  }
};

export const getIconFromType = (type: types.CameraEvent["type"]) =>
  iconMap[type];

// Base hook that contains shared logic
const useTimespansBase = (
  date: Dayjs | null,
  callback: (message: types.HlsAvailableTimespans) => void,
  debounce = 5,
  enabled: boolean | null = null,
) => {
  const { selectedCameras } = useCameraStore();
  const camerasQuery = useCameras({});

  let _enabled: boolean;
  if (enabled === null) {
    _enabled =
      !!camerasQuery.data &&
      camerasQuery.data.cameras &&
      selectedCameras.some((camera) => camera in camerasQuery.data.cameras);
  } else {
    _enabled = enabled;
  }

  useSubscribeTimespans(
    selectedCameras,
    date ? date.format("YYYY-MM-DD") : null,
    callback,
    _enabled,
    debounce,
  );
};

export const useTimespans = (
  date: Dayjs | null,
  debounce = 5,
  enabled: boolean | null = null,
) => {
  const { availableTimespans, setAvailableTimespans, availableTimespansRef } =
    useAvailableTimespansStore();

  const timespanCallback = useCallback(
    (message: types.HlsAvailableTimespans) => {
      setAvailableTimespans(message.timespans);
    },
    [setAvailableTimespans],
  );

  useTimespansBase(date, timespanCallback, debounce, enabled);

  return { availableTimespans, availableTimespansRef };
};

// Use this in favor of useTimespans when you need to access the available
// timespans without re-rendering the component
export const useTimespansRef = (
  date: Dayjs | null,
  debounce = 5,
  enabled: boolean | null = null,
) => {
  const { availableTimespansRef } = useAvailableTimespansStore(
    useShallow((state) => ({
      availableTimespansRef: state.availableTimespansRef,
    })),
  );

  const timespanCallback = useCallback(
    (message: types.HlsAvailableTimespans) => {
      availableTimespansRef.current = message.timespans;
    },
    [availableTimespansRef],
  );

  useTimespansBase(date, timespanCallback, debounce, enabled);

  return { availableTimespansRef };
};

// Error codes for HLS errors
export enum HlsErrorCodes {
  TIMESPAN_MISSING = "TIMESPAN_MISSING",
}
// Mapping of error codes to human-readable messages
const hlsErrorMessages: Record<HlsErrorCodes, string> = {
  [HlsErrorCodes.TIMESPAN_MISSING]:
    "Video segment is missing for the selected period.",
};
// Function to translate error code to human-readable message
export const translateErrorCode = (code: HlsErrorCodes): string =>
  hlsErrorMessages[code] || "An unknown error occurred.";
