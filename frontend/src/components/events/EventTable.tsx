import Box from "@mui/material/Box";
import Divider from "@mui/material/Divider";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";
import dayjs, { Dayjs } from "dayjs";
import { memo } from "react";
import { ReactComponent as ServerDown } from "svg/undraw/server_down.svg";

import { Error } from "components/error/Error";
import { EventTableItem } from "components/events/EventTableItem";
import { Loading } from "components/loading/Loading";
import * as types from "lib/types";

type EventTableProps = {
  camera: types.Camera;
  date: Dayjs | null;
  setSelectedRecording: (recording: types.Recording) => void;
};

export const EventTable = memo(
  ({ camera, date, setSelectedRecording }: EventTableProps) => {
    const recordingsQuery = useQuery<types.RecordingsCamera>({
      queryKey: [`/recordings/${camera.identifier}`],
    });

    if (recordingsQuery.isError) {
      return (
        <Error
          text={`Error loading recordings`}
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
        <Error
          text={`No recordings found for ${camera.name}`}
          image={
            <ServerDown width={150} height={150} role="img" aria-label="Void" />
          }
        />
      );
    }

    const formattedDate = dayjs(date).format("YYYY-MM-DD");

    return (
      <Box>
        {formattedDate in recordingsQuery.data ? (
          <Grid container direction="row" columns={1}>
            {Object.values(
              recordingsQuery.data[dayjs(date).format("YYYY-MM-DD")]
            )
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
  }
);
