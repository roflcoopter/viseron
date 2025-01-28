import AirIcon from "@mui/icons-material/Air";
import DirectionsCarIcon from "@mui/icons-material/DirectionsCar";
import PersonIcon from "@mui/icons-material/DirectionsWalk";
import FaceIcon from "@mui/icons-material/Face";
import ImageSearchIcon from "@mui/icons-material/ImageSearch";
import PetsIcon from "@mui/icons-material/Pets";
import VideoFileIcon from "@mui/icons-material/VideoFile";
import dayjs, { Dayjs } from "dayjs";
import Hls, { Fragment } from "hls.js";
import { useCallback, useMemo, useState } from "react";
import { create } from "zustand";
import { persist } from "zustand/middleware";

import LicensePlateRecognitionIcon from "components/icons/LicensePlateRecognition";
import { useCameras, useCamerasFailed } from "lib/api/cameras";
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

type Filters = {
  [key in types.CameraEvent["type"]]: {
    label: string;
    checked: boolean;
  };
};

interface FilterState {
  filters: Filters;
  setFilters: (filters: Filters) => void;
  toggleFilter: (filterKey: types.CameraEvent["type"]) => void;
}

export const useFilterStore = create<FilterState>()(
  persist(
    (set) => ({
      filters: {
        motion: { label: "Motion", checked: true },
        object: { label: "Object", checked: true },
        recording: { label: "Recording", checked: true },
        face_recognition: { label: "Face Recognition", checked: true },
        license_plate_recognition: {
          label: "License Plate Recognition",
          checked: true,
        },
      },
      setFilters: (filters) => set({ filters }),
      toggleFilter: (filterKey: types.CameraEvent["type"]) => {
        set((state) => {
          const newFilters = { ...state.filters };
          newFilters[filterKey].checked = !newFilters[filterKey].checked;
          return { filters: newFilters };
        });
      },
    }),
    { name: "filter-store" },
  ),
);

type Cameras = {
  [key: string]: boolean;
};

interface CameraState {
  cameras: Cameras;
  selectedCameras: string[];
  toggleCamera: (cameraIdentifier: string) => void;
  selectSingleCamera: (cameraIdentifier: string) => void;
  selectionOrder: string[];
}

export const useCameraStore = create<CameraState>()(
  persist(
    (set) => ({
      cameras: {},
      selectedCameras: [],
      toggleCamera: (cameraIdentifier) => {
        set((state) => {
          const newCameras = { ...state.cameras };
          newCameras[cameraIdentifier] = !newCameras[cameraIdentifier];
          let newSelectionOrder = [...state.selectionOrder];
          if (newCameras[cameraIdentifier]) {
            newSelectionOrder.push(cameraIdentifier);
          } else {
            newSelectionOrder = newSelectionOrder.filter(
              (id) => id !== cameraIdentifier,
            );
          }
          return {
            cameras: newCameras,
            selectedCameras: Object.entries(newCameras)
              .filter(([_key, value]) => value)
              .map(([key]) => key),
            selectionOrder: newSelectionOrder,
          };
        });
      },
      selectSingleCamera: (cameraIdentifier) => {
        set((state) => {
          const newCameras = { ...state.cameras };
          Object.keys(newCameras).forEach((key) => {
            newCameras[key] = key === cameraIdentifier;
          });
          return {
            cameras: newCameras,
            selectedCameras: [cameraIdentifier],
            selectionOrder: [cameraIdentifier],
          };
        });
      },
      selectionOrder: [],
    }),
    { name: "camera-store" },
  ),
);

export const useFilteredCameras = () => {
  const camerasQuery = useCameras({});
  const failedCamerasQuery = useCamerasFailed({});

  // Combine the two queries into one object
  const cameraData: types.CamerasOrFailedCameras = useMemo(() => {
    if (!camerasQuery.data && !failedCamerasQuery.data) {
      return {};
    }
    return {
      ...camerasQuery.data,
      ...failedCamerasQuery.data,
    };
  }, [camerasQuery.data, failedCamerasQuery.data]);

  const { selectedCameras } = useCameraStore();
  return useMemo(
    () =>
      Object.keys(cameraData)
        .filter((key) => selectedCameras.includes(key))
        .reduce((obj: types.CamerasOrFailedCameras, key) => {
          obj[key] = cameraData[key];
          return obj;
        }, {}),
    [cameraData, selectedCameras],
  );
};

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
  availableTimespan: null,
  activityLineVariant: null,
};

export type TimelineItem = {
  time: number;
  timedEvent: null | types.CameraMotionEvent | types.CameraRecordingEvent;
  snapshotEvents: null | types.CameraSnapshotEvents;
  availableTimespan: null | types.HlsAvailableTimespan;
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
export const createActivityLineItem = (
  startRef: React.MutableRefObject<number>,
  indexStart: number,
  indexEnd: number,
  event: types.CameraEvent | types.HlsAvailableTimespan,
  eventType: "availableTimespan" | "timedEvent",
) => {
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
};

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
    (event) => filters[event.type].checked,
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
        timespan,
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

  // Loop over events where type is object
  filteredEvents
    .filter(
      (cameraEvent): cameraEvent is types.CameraObjectEvent =>
        cameraEvent.type === "object",
    )
    .forEach((cameraEvent) => {
      addSnapshotEvent(startRef, timelineItems, cameraEvent);
    });

  filteredEvents
    .filter(
      (
        cameraEvent,
      ): cameraEvent is
        | types.CameraFaceRecognitionEvent
        | types.CameraLicensePlateRecognitionEvent =>
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
    typeMap.get(type)!.push(event);
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

export const useTimespans = (
  date: Dayjs | null,
  debounce = 5,
  enabled: boolean | null = null,
) => {
  const { selectedCameras } = useCameraStore();
  const camerasQuery = useCameras({});
  const [availableTimespans, setAvailableTimespans] = useState<
    types.HlsAvailableTimespan[]
  >([]);

  const timespanCallback = useCallback(
    (message: types.HlsAvailableTimespans) => {
      setAvailableTimespans(message.timespans);
    },
    [],
  );

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
    timespanCallback,
    _enabled,
    debounce,
  );

  return availableTimespans;
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
