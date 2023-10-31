import { useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import dayjs, { Dayjs } from "dayjs";
import { useState } from "react";
import { ReactComponent as ServerDown } from "svg/undraw/server_down.svg";
import "video.js/dist/video-js.css";

import { Error } from "components/error/Error";
import { Layout, LayoutSmall } from "components/events/Layouts";
import { Loading } from "components/loading/Loading";
import { useTitle } from "hooks/UseTitle";
import { useCameras } from "lib/api/cameras";
import * as types from "lib/types";

const Events = () => {
  useTitle("Events");
  const theme = useTheme();
  const matches = useMediaQuery(theme.breakpoints.up("sm"));

  const cameraQuery = useCameras({});
  const [selectedCamera, setSelectedCamera] = useState<types.Camera | null>(
    null
  );
  const [selectedRecording, setSelectedRecording] =
    useState<types.Recording | null>(null);
  const [date, setDate] = useState<Dayjs | null>(dayjs());

  const changeSource = (
    ev: React.MouseEvent<HTMLButtonElement, MouseEvent>,
    camera: types.Camera
  ) => {
    setSelectedCamera(camera);
  };

  if (cameraQuery.isError) {
    return (
      <Error
        text={`Error loading cameras`}
        image={
          <ServerDown width={150} height={150} role="img" aria-label="Void" />
        }
      />
    );
  }

  if (cameraQuery.isLoading) {
    return <Loading text="Loading Camera" />;
  }

  if (!cameraQuery.data) {
    return null;
  }

  if (matches) {
    return (
      <Layout
        cameras={cameraQuery.data}
        selectedCamera={selectedCamera}
        selectedRecording={selectedRecording}
        setSelectedRecording={setSelectedRecording}
        changeSource={changeSource}
        date={date}
        setDate={setDate}
      />
    );
  }
  return (
    <LayoutSmall
      cameras={cameraQuery.data}
      selectedCamera={selectedCamera}
      selectedRecording={selectedRecording}
      setSelectedRecording={setSelectedRecording}
      changeSource={changeSource}
      date={date}
      setDate={setDate}
    />
  );
};

export default Events;
