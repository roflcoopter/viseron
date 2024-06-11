import Card from "@mui/material/Card";
import CardMedia from "@mui/material/CardMedia";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import Hls from "hls.js";

import { CameraNameOverlay } from "components/camera/CameraNameOverlay";
import { TimelinePlayer } from "components/events/timeline/TimelinePlayer";
import { getSrc } from "components/events/utils";
import VideoPlayerPlaceholder from "components/videoplayer/VideoPlayerPlaceholder";
import * as types from "lib/types";

dayjs.extend(utc);

type PlayerCardProps = {
  camera: types.Camera | types.FailedCamera | null;
  selectedEvent: types.CameraEvent | null;
  requestedTimestamp: number | null;
  selectedTab: "events" | "timeline";
  hlsRef: React.MutableRefObject<Hls | null>;
  playerCardRef: React.RefObject<HTMLDivElement>;
};

export const PlayerCard = ({
  camera,
  selectedEvent,
  requestedTimestamp,
  hlsRef,
  playerCardRef,
}: PlayerCardProps) => {
  const src = camera && selectedEvent ? getSrc(selectedEvent) : undefined;

  return (
    <Card
      ref={playerCardRef}
      variant="outlined"
      sx={(theme) => ({
        marginBottom: theme.margin,
        position: "relative",
      })}
    >
      {camera && <CameraNameOverlay camera={camera} />}
      <CardMedia>
        {camera && requestedTimestamp ? (
          <TimelinePlayer
            containerRef={playerCardRef}
            hlsRef={hlsRef}
            camera={camera}
            requestedTimestamp={requestedTimestamp}
          />
        ) : (
          <VideoPlayerPlaceholder
            aspectRatio={camera ? camera.width / camera.height : undefined}
            text={
              camera && src
                ? undefined
                : camera
                  ? "Select an event"
                  : "Select a camera"
            }
            src={src}
          />
        )}
      </CardMedia>
    </Card>
  );
};
