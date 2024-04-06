import Box from "@mui/material/Box";
import Divider from "@mui/material/Divider";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import dayjs, { Dayjs } from "dayjs";
import { memo, useEffect } from "react";
import { forceCheck } from "react-lazyload";
import ServerDown from "svg/undraw/server_down.svg?react";

import { ErrorMessage } from "components/error/ErrorMessage";
import { EventTableItem } from "components/events/EventTableItem";
import { Loading } from "components/loading/Loading";
import { useRecordings } from "lib/api/recordings";
import { throttle } from "lib/helpers";
import * as types from "lib/types";

const useOnScroll = (parentRef: React.RefObject<HTMLDivElement>) => {
  useEffect(() => {
    const container = parentRef.current;
    if (!container) return () => {};

    const throttleForceCheck = throttle(() => {
      forceCheck();
    }, 100);
    container.addEventListener("scroll", throttleForceCheck);

    return () => {
      container.removeEventListener("scroll", throttleForceCheck);
    };
  });
};

type EventTableProps = {
  parentRef: React.RefObject<HTMLDivElement>;
  camera: types.Camera | types.FailedCamera;
  date: Dayjs | null;
  selectedRecording: types.Recording | null;
  setSelectedRecording: (recording: types.Recording) => void;
};

export const EventTable = memo(
  ({
    parentRef,
    camera,
    date,
    selectedRecording,
    setSelectedRecording,
  }: EventTableProps) => {
    const formattedDate = dayjs(date).format("YYYY-MM-DD");
    const recordingsQuery = useRecordings({
      camera_identifier: camera.identifier,
      failed: camera.failed,
      date: formattedDate,
      configOptions: { enabled: !!date },
    });

    useOnScroll(parentRef);

    if (recordingsQuery.isError) {
      return (
        <ErrorMessage
          text={"Error loading recordings"}
          subtext={recordingsQuery.error.message}
          image={
            <ServerDown width={150} height={150} role="img" aria-label="Void" />
          }
        />
      );
    }

    if (recordingsQuery.isLoading) {
      return <Loading text="Loading Recordings" fullScreen={false} />;
    }

    if (!recordingsQuery.data) {
      return (
        <ErrorMessage
          text={`No recordings found for ${camera.name}`}
          image={
            <ServerDown width={150} height={150} role="img" aria-label="Void" />
          }
        />
      );
    }

    return (
      <Box>
        {formattedDate in recordingsQuery.data ? (
          <Grid container direction="row" columns={1}>
            {Object.values(recordingsQuery.data[formattedDate])
              .sort()
              .reverse()
              .map((recording) => (
                <Grid
                  item
                  xs={12}
                  sm={12}
                  md={12}
                  lg={12}
                  xl={12}
                  key={recording.id}
                >
                  <EventTableItem
                    camera={camera}
                    recording={recording}
                    setSelectedRecording={setSelectedRecording}
                    selected={
                      !!selectedRecording &&
                      selectedRecording.id === recording.id
                    }
                  />
                  <Divider sx={{ marginTop: "5px", marginBottom: "5px" }} />
                </Grid>
              ))}
          </Grid>
        ) : (
          <Typography align="center" padding={2}>
            No recordings found for {formattedDate}
          </Typography>
        )}
      </Box>
    );
  },
);
