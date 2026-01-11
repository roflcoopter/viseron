import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Grow from "@mui/material/Grow";
import { Dayjs } from "dayjs";
import { useState } from "react";
import { useParams } from "react-router-dom";
import ServerDown from "svg/undraw/server_down.svg?react";
import VoidSvg from "svg/undraw/void.svg?react";

import { ErrorMessage } from "components/error/ErrorMessage";
import { Loading } from "components/loading/Loading";
import RecordingCard from "components/recording/RecordingCard";
import { RecordingHeaderDaily } from "components/recording/RecordingHeaderDaily";
import { useTitle } from "hooks/UseTitle";
import { useCamera } from "lib/api/camera";
import { useRecordings } from "lib/api/recordings";
import {
  getDayjsFromDateString,
  getDayjsFromDateTimeString,
  objHasValues,
} from "lib/helpers";
import * as types from "lib/types";

type CameraRecordingsDailyParams = {
  camera_identifier: string;
  date: string;
};
function CameraRecordingsDaily() {
  const { camera_identifier, date } = useParams<
    keyof CameraRecordingsDailyParams
  >() as CameraRecordingsDailyParams;

  const [startTime, setStartTime] = useState<Dayjs | null>(null);
  const [endTime, setEndTime] = useState<Dayjs | null>(null);
  const [triggerTypeFilter, setTriggerTypeFilter] = useState<string[]>([]);

  const recordingsQuery = useRecordings({
    camera_identifier,
    date,
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
    !objHasValues<types.RecordingsCamera>(recordingsQuery.data) ||
    !objHasValues(recordingsQuery.data[date])
  ) {
    return (
      <ErrorMessage
        text={`No recordings for ${cameraQuery.data.name} - ${date}`}
        image={
          <VoidSvg width={150} height={150} role="img" aria-label="Void" />
        }
      />
    );
  }

  const allRecordings = Object.keys(recordingsQuery.data[date]);
  const totalVideos = allRecordings.length;

  const filteredRecordings =
    startTime && endTime
      ? allRecordings.filter((recording) => {
          const recordingData = recordingsQuery.data[date][recording];
          const recordingTime = getDayjsFromDateTimeString(
            recordingData.start_time,
          );
          const timeMatch =
            (recordingTime.isAfter(startTime) ||
              recordingTime.isSame(startTime)) &&
            (recordingTime.isBefore(endTime) || recordingTime.isSame(endTime));

          const triggerTypeMatch =
            triggerTypeFilter.length === 0 ||
            (recordingData.trigger_type &&
              triggerTypeFilter.includes(recordingData.trigger_type));

          return timeMatch && triggerTypeMatch;
        })
      : allRecordings.filter((recording) => {
          const recordingData = recordingsQuery.data[date][recording];
          return (
            triggerTypeFilter.length === 0 ||
            (recordingData.trigger_type &&
              triggerTypeFilter.includes(recordingData.trigger_type))
          );
        });

  const handleStartTimeChange = (newValue: Dayjs | null) => {
    if (newValue) {
      // Set time with the correct date context
      const timeWithDate = getDayjsFromDateString(date)
        .hour(newValue.hour())
        .minute(newValue.minute())
        .second(newValue.second());
      setStartTime(timeWithDate);
    } else {
      setStartTime(null);
    }
  };

  const handleEndTimeChange = (newValue: Dayjs | null) => {
    if (newValue) {
      // Set time with the correct date context
      const timeWithDate = getDayjsFromDateString(date)
        .hour(newValue.hour())
        .minute(newValue.minute())
        .second(newValue.second());
      setEndTime(timeWithDate);
    } else {
      setEndTime(null);
    }
  };

  const handleClearTimes = () => {
    setStartTime(null);
    setEndTime(null);
  };

  const handleTriggerTypeChange = (
    _event: React.MouseEvent<HTMLElement>,
    newTypes: string[],
  ) => {
    setTriggerTypeFilter(newTypes);
  };

  return (
    <Container sx={{ paddingX: { xs: 1, md: 2 }, paddingY: 0.5 }}>
      <RecordingHeaderDaily
        camera={cameraQuery.data}
        date={date}
        totalVideos={totalVideos}
        startTime={startTime}
        endTime={endTime}
        triggerTypeFilter={triggerTypeFilter}
        onStartTimeChange={handleStartTimeChange}
        onEndTimeChange={handleEndTimeChange}
        onClearTimes={handleClearTimes}
        onTriggerTypeChange={handleTriggerTypeChange}
      />

      <Grid container direction="row" spacing={1}>
        {filteredRecordings.reverse().map((recording) => (
          <Grow in appear key={recording}>
            <Grid
              key={recording}
              size={{
                xs: 12,
                sm: 12,
                md: 6,
                lg: 4,
                xl: 3,
              }}
            >
              <RecordingCard
                camera={cameraQuery.data}
                recording={recordingsQuery.data[date][recording]}
              />
            </Grid>
          </Grow>
        ))}
      </Grid>
    </Container>
  );
}

export default CameraRecordingsDaily;
