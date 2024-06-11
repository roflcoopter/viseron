import { useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import dayjs, { Dayjs } from "dayjs";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import ServerDown from "svg/undraw/server_down.svg?react";
import "video.js/dist/video-js.css";

import { ErrorMessage } from "components/error/ErrorMessage";
import { Layout, LayoutSmall } from "components/events/Layouts";
import { Loading } from "components/loading/Loading";
import { useTitle } from "hooks/UseTitle";
import { useCameras, useCamerasFailed } from "lib/api/cameras";
import { insertURLParameter, objHasValues, objIsEmpty } from "lib/helpers";
import * as types from "lib/types";

const getDefaultTab = (searchParams: URLSearchParams) => {
  if (
    searchParams.has("tab") &&
    (searchParams.get("tab") === "events" ||
      searchParams.get("tab") === "timeline")
  ) {
    return searchParams.get("tab") as "events" | "timeline";
  }
  return "events";
};

const Events = () => {
  useTitle("Events");
  const theme = useTheme();
  const matches = useMediaQuery(theme.breakpoints.up("sm"));
  const [searchParams] = useSearchParams();
  const camerasQuery = useCameras({});
  const failedCamerasQuery = useCamerasFailed({});
  const [selectedCamera, setSelectedCamera] = useState<
    types.Camera | types.FailedCamera | null
  >(null);

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

  const [selectedEvent, setSelectedEvent] = useState<types.CameraEvent | null>(
    null,
  );
  const [date, setDate] = useState<Dayjs | null>(
    searchParams.has("date")
      ? dayjs(searchParams.get("date") as string)
      : dayjs(),
  );
  const [requestedTimestamp, setRequestedTimestamp] = useState<number | null>(
    null,
  );
  const [selectedTab, setSelectedTab] = useState<"events" | "timeline">(
    getDefaultTab(searchParams),
  );
  const changeSelectedCamera = (
    ev: React.MouseEvent<HTMLButtonElement, MouseEvent>,
    camera: types.Camera | types.FailedCamera,
  ) => {
    setSelectedCamera(camera);
    setRequestedTimestamp(null);
    setSelectedEvent(null);
  };

  useEffect(() => {
    if (
      objHasValues(cameraData) &&
      searchParams.has("camera") &&
      !selectedCamera
    ) {
      setSelectedCamera(cameraData[searchParams.get("camera") as string]);
    }
  }, [cameraData, searchParams, selectedCamera]);
  useEffect(() => {
    if (selectedCamera) {
      insertURLParameter("camera", selectedCamera.identifier);
    }
  }, [selectedCamera]);
  useEffect(() => {
    if (date) {
      insertURLParameter("date", date.format("YYYY-MM-DD"));
    }
  }, [date]);

  if (camerasQuery.isError) {
    return (
      <ErrorMessage
        text={`Error loading cameras`}
        subtext={camerasQuery.error.message}
        image={
          <ServerDown
            width={150}
            height={150}
            role="img"
            aria-label="Server down"
          />
        }
      />
    );
  }

  if (camerasQuery.isLoading || failedCamerasQuery.isLoading) {
    return <Loading text="Loading Camera" />;
  }

  if (objIsEmpty(cameraData)) {
    return null;
  }

  const LayoutVariant = matches ? Layout : LayoutSmall;
  return (
    <LayoutVariant
      cameras={cameraData}
      selectedCamera={selectedCamera}
      selectedEvent={selectedEvent}
      setSelectedEvent={setSelectedEvent}
      changeSelectedCamera={changeSelectedCamera}
      date={date}
      setDate={setDate}
      requestedTimestamp={requestedTimestamp}
      setRequestedTimestamp={setRequestedTimestamp}
      selectedTab={selectedTab}
      setSelectedTab={setSelectedTab}
    />
  );
};

export default Events;
