import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Grow from "@mui/material/Grow";
import dayjs, { Dayjs } from "dayjs";
import { useState } from "react";
import { useParams } from "react-router-dom";
import ServerDown from "svg/undraw/server_down.svg?react";
import VoidSvg from "svg/undraw/void.svg?react";

import { ErrorMessage } from "components/error/ErrorMessage";
import { Loading } from "components/loading/Loading";
import RecordingCardDaily from "components/recording/RecordingCardDaily";
import { RecordingHeader } from "components/recording/RecordingHeader";
import { useTitle } from "hooks/UseTitle";
import { useCamera } from "lib/api/camera";
import { useRecordings } from "lib/api/recordings";
import { objHasValues } from "lib/helpers";
import * as types from "lib/types";

type CameraRecordingsParams = {
  camera_identifier: string;
};
function CameraRecordings() {
  const { camera_identifier } = useParams<
    keyof CameraRecordingsParams
  >() as CameraRecordingsParams;
  const [startDate, setStartDate] = useState<Dayjs | null>(null);
  const [endDate, setEndDate] = useState<Dayjs | null>(null);

  const recordingsQuery = useRecordings({
    camera_identifier,
    latest: true,
    daily: true,
    failed: true,
  });
  const cameraQuery = useCamera(camera_identifier, true);

  useTitle(
    `Recordings${cameraQuery.data ? ` | ${cameraQuery.data.name}` : ""}`,
  );

  if (recordingsQuery.isError || cameraQuery.isError) {
    return (
      <ErrorMessage
        text="Error loading recordings"
        subtext={recordingsQuery.error?.message || cameraQuery.error?.message}
        image={
          <ServerDown width={150} height={150} role="img" aria-label="Void" />
        }
      />
    );
  }

  if (recordingsQuery.isPending || cameraQuery.isPending) {
    return <Loading text="Loading Recordings" />;
  }

  if (
    !recordingsQuery.data ||
    !objHasValues<types.RecordingsCamera>(recordingsQuery.data)
  ) {
    return (
      <ErrorMessage
        text={`No recordings for ${cameraQuery.data.name}`}
        image={
          <VoidSvg width={150} height={150} role="img" aria-label="Void" />
        }
      />
    );
  }

  const availableDates = Object.keys(recordingsQuery.data);
  const totalDays = availableDates.length;
  const filteredDates =
    startDate && endDate
      ? availableDates.filter((date) => {
          const d = dayjs(date);
          return (
            (d.isAfter(startDate, "day") || d.isSame(startDate, "day")) &&
            (d.isBefore(endDate, "day") || d.isSame(endDate, "day"))
          );
        })
      : availableDates;

  const handleClearDates = () => {
    setStartDate(null);
    setEndDate(null);
  };

  return (
    <Container sx={{ paddingX: 2 }}>
      <RecordingHeader
        camera={cameraQuery.data}
        totalDays={totalDays}
        availableDates={availableDates}
        startDate={startDate}
        endDate={endDate}
        onStartDateChange={setStartDate}
        onEndDateChange={setEndDate}
        onClearDates={handleClearDates}
      />

      <Grid container direction="row" spacing={1}>
        {filteredDates
          .sort()
          .reverse()
          .map((date) => (
            <Grow in appear key={date}>
              <Grid
                key={date}
                size={{
                  xs: 12,
                  sm: 12,
                  md: 6,
                  lg: 4,
                  xl: 3,
                }}
              >
                <RecordingCardDaily
                  camera={cameraQuery.data}
                  recording={Object.values(recordingsQuery.data[date])[0]}
                  date={date}
                />
              </Grid>
            </Grow>
          ))}
      </Grid>
    </Container>
  );
}

export default CameraRecordings;
