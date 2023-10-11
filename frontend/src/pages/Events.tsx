/* eslint-disable @typescript-eslint/no-unused-vars */
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Container from "@mui/material/Container";
import Typography from "@mui/material/Typography";
import dayjs, { Dayjs } from "dayjs";
import { useState } from "react";
import { ReactComponent as ServerDown } from "svg/undraw/server_down.svg";
import "video.js/dist/video-js.css";

import { Error } from "components/error/Error";
import { PlayerCard } from "components/events/EventPlayerCard";
import { EventTable } from "components/events/EventTable";
import { EventsCameraGrid } from "components/events/EventsCameraGrid";
import { Loading } from "components/loading/Loading";
import { useTitle } from "hooks/UseTitle";
import { useCameras } from "lib/api/cameras";
import * as types from "lib/types";

const Events = () => {
  useTitle("Events");
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

  return (
    <Container maxWidth={false} style={{ display: "flex" }}>
      <div
        style={{
          width: "100%",
          display: "flex",
          flexDirection: "column",
          marginRight: "10px",
        }}
      >
        <PlayerCard camera={selectedCamera} recording={selectedRecording} />
        <EventsCameraGrid
          cameras={cameraQuery.data}
          changeSource={changeSource}
        ></EventsCameraGrid>
      </div>
      <Card
        variant="outlined"
        sx={{ width: "550px", height: "90vh", overflow: "auto" }}
      >
        <CardContent sx={{ padding: 0 }}>
          {selectedCamera ? (
            <EventTable
              camera={selectedCamera}
              date={date}
              onDateChange={(value) => setDate(value)}
              setSelectedRecording={setSelectedRecording}
            />
          ) : (
            <Typography align="center" sx={{ marginTop: "20px" }}>
              Select a camera to load events
            </Typography>
          )}
        </CardContent>
      </Card>
    </Container>
  );
};

export default Events;
