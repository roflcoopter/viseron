import dayjs, { Dayjs } from "dayjs";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import ServerDown from "svg/undraw/server_down.svg?react";
import { useShallow } from "zustand/react/shallow";

import { useCameraStore } from "components/camera/useCameraStore";
import { ErrorMessage } from "components/error/ErrorMessage";
import { Layout } from "components/events/Layouts";
import { useReferencePlayerStore } from "components/events/utils";
import { Loading } from "components/loading/Loading";
import { useHideScrollbar } from "hooks/UseHideScrollbar";
import { useTitle } from "hooks/UseTitle";
import { useCamerasAll } from "lib/api/cameras";
import {
  insertURLParameter,
  objHasValues,
  objIsEmpty,
  removeURLParameter,
} from "lib/helpers";

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

function Events() {
  useTitle("Events");
  useHideScrollbar();
  const [searchParams] = useSearchParams();
  const { selectSingleCamera } = useCameraStore();
  const { setRequestedTimestamp } = useReferencePlayerStore(
    useShallow((state) => ({
      setRequestedTimestamp: state.setRequestedTimestamp,
    })),
  );
  const camerasAll = useCamerasAll();

  const [date, setDate] = useState<Dayjs | null>(
    searchParams.has("date")
      ? dayjs(searchParams.get("date") as string)
      : dayjs(),
  );
  const [selectedTab, setSelectedTab] = useState<"events" | "timeline">(
    getDefaultTab(searchParams),
  );

  useEffect(() => {
    if (objHasValues(camerasAll.combinedData) && searchParams.has("camera")) {
      selectSingleCamera(
        camerasAll.combinedData[searchParams.get("camera") as string]
          .identifier,
      );
      searchParams.delete("camera");
      const newUrl = removeURLParameter(window.location.href, "camera");
      window.history.pushState({ path: newUrl }, "", newUrl);
    }
  }, [camerasAll.combinedData, searchParams, selectSingleCamera]);

  useEffect(() => {
    if (date) {
      insertURLParameter("date", date.format("YYYY-MM-DD"));
    }
  }, [date]);

  useEffect(() => {
    if (searchParams.has("timestamp")) {
      const timestamp = searchParams.get("timestamp");
      if (timestamp && !isNaN(Number(timestamp))) {
        setRequestedTimestamp(Number(timestamp));
      }
      searchParams.delete("timestamp");
      const newUrl = removeURLParameter(window.location.href, "timestamp");
      window.history.pushState({ path: newUrl }, "", newUrl);
    }
  }, [searchParams, setRequestedTimestamp]);

  if (camerasAll.cameras.isError) {
    return (
      <ErrorMessage
        text="Error loading cameras"
        subtext={camerasAll.cameras.error.message}
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

  if (camerasAll.cameras.isPending || camerasAll.failedCameras.isPending) {
    return <Loading text="Loading Cameras" />;
  }

  if (objIsEmpty(camerasAll.combinedData)) {
    return null;
  }

  return (
    <Layout
      date={date}
      setDate={setDate}
      selectedTab={selectedTab}
      setSelectedTab={setSelectedTab}
    />
  );
}

export default Events;
