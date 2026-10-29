import {
  Maximize,
  Minimize,
  PauseFilled,
  PlayFilledAlt,
  Repeat,
} from "@carbon/icons-react";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import IconButton from "@mui/material/IconButton";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Slider from "@mui/material/Slider";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { RefObject, useCallback, useMemo, useRef, useState } from "react";

import {
  buildTimelapsePlaylist,
  frameAt,
  frameIndexAtOrAfter,
  frameTime,
  isBuffered,
} from "components/timelapse/playlist";
import { useTimelapseHls } from "components/timelapse/useTimelapseHls";
import {
  usePlaybackRate,
  useVideoPlayback,
} from "components/timelapse/useVideoPlayback";
import {
  DEFAULT_FPS,
  FPS_OPTIONS,
  formatTimestamp,
} from "components/timelapse/utils";
import { useFullscreen } from "context/FullscreenContext";
import { useTimeout } from "hooks/UseTimeout";
import * as types from "lib/types";

const MAX_GAP_MARKERS = 100;
// Gaps shorter than this are normal jitter between frames
const MIN_GAP_SECONDS = 60;
// Unbuffered positions are only loaded once the scrubbing thumb rests here
const SCRUB_SEEK_DELAY_MS = 300;

// Indexes of frames that are preceded by a gap in the recording
export function findGaps(frames: types.TimelapseFrame[], step: number | null) {
  if (frames.length < 3) {
    return [];
  }
  const spacingBefore = (i: number) =>
    frames[i].timestamp - frames[i - 1].timestamp;
  const indexes = frames.map((_, i) => i).slice(1);

  // Without a downsampling step, the median spacing is the normal one
  const spacings = indexes.map(spacingBefore).sort((a, b) => a - b);
  const normal = step ?? spacings[Math.floor(spacings.length / 2)];
  const threshold = Math.max(normal * 3, MIN_GAP_SECONDS);

  // Only the longest gaps get a marker
  return indexes
    .filter((i) => spacingBefore(i) > threshold)
    .sort((a, b) => spacingBefore(b) - spacingBefore(a))
    .slice(0, MAX_GAP_MARKERS)
    .sort((a, b) => a - b);
}

type VideoAreaProps = {
  videoRef: RefObject<HTMLVideoElement | null>;
  stream: types.TimelapseStream;
  loop: boolean;
  isFullscreen: boolean;
  stillFrame: types.TimelapseFrame | null;
  error: string | null;
  buffering: boolean;
  onClick: () => void;
};

function VideoArea({
  videoRef,
  stream,
  loop,
  isFullscreen,
  stillFrame,
  error,
  buffering,
  onClick,
}: VideoAreaProps) {
  return (
    <Box
      onClick={onClick}
      sx={{
        position: "relative",
        flex: 1,
        minHeight: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "black",
        cursor: "pointer",
      }}
    >
      <video
        ref={videoRef}
        loop={loop}
        muted
        playsInline
        style={{
          display: "block",
          width: "100%",
          height: isFullscreen ? "100%" : "auto",
          maxHeight: isFullscreen ? undefined : "70vh",
          aspectRatio: `${stream.width} / ${stream.height}`,
          objectFit: "contain",
        }}
      />
      {stillFrame ? (
        <Box
          component="img"
          src={stillFrame.path}
          alt=""
          data-testid="timelapse-still"
          sx={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            objectFit: "contain",
            backgroundColor: "black",
          }}
        />
      ) : null}
      {error ? (
        <Typography
          sx={{
            position: "absolute",
            color: "white",
            backgroundColor: "rgba(0, 0, 0, 0.6)",
            paddingX: 1,
            borderRadius: 1,
          }}
        >
          {error}
        </Typography>
      ) : null}
      {buffering && !error ? (
        <CircularProgress
          aria-label="Buffering"
          sx={{ position: "absolute" }}
        />
      ) : null}
    </Box>
  );
}

type FrameSliderProps = {
  frames: types.TimelapseFrame[];
  index: number;
  gaps: number[];
  onScrub: (index: number) => void;
  onScrubEnd: (index: number) => void;
};

function FrameSlider({
  frames,
  index,
  gaps,
  onScrub,
  onScrubEnd,
}: FrameSliderProps) {
  return (
    <Box sx={{ paddingX: 2, paddingTop: 1 }}>
      <Slider
        aria-label="Frame"
        size="small"
        min={0}
        max={Math.max(frames.length - 1, 0)}
        value={index}
        marks={gaps.map((gap) => ({ value: gap }))}
        step={1}
        valueLabelDisplay="auto"
        valueLabelFormat={(value) =>
          frames[value] ? formatTimestamp(frames[value].timestamp) : ""
        }
        onChange={(_event, value) => onScrub(value as number)}
        onChangeCommitted={(_event, value) => onScrubEnd(value as number)}
        sx={{
          // The value changes every animation frame during playback, which a
          // position transition lags behind
          "& .MuiSlider-track": { transition: "none" },
          "& .MuiSlider-thumb": {
            transition: (theme) =>
              theme.transitions.create("box-shadow", {
                duration: theme.transitions.duration.shortest,
              }),
          },
          "& .MuiSlider-mark": {
            backgroundColor: "warning.main",
            height: 10,
            width: 2,
          },
        }}
      />
    </Box>
  );
}

type PlayerControlsProps = {
  playing: boolean;
  index: number;
  frameCount: number;
  fps: number;
  loop: boolean;
  isFullscreen: boolean;
  onTogglePlaying: () => void;
  onFpsChange: (fps: number) => void;
  onLoopChange: (loop: boolean) => void;
  onToggleFullscreen: () => void;
};

function PlayerControls({
  playing,
  index,
  frameCount,
  fps,
  loop,
  isFullscreen,
  onTogglePlaying,
  onFpsChange,
  onLoopChange,
  onToggleFullscreen,
}: PlayerControlsProps) {
  return (
    <Stack
      direction="row"
      alignItems="center"
      spacing={1}
      sx={{ paddingX: 1, paddingBottom: 1 }}
    >
      <Tooltip title={playing ? "Pause" : "Play"}>
        <IconButton
          aria-label={playing ? "Pause" : "Play"}
          onClick={onTogglePlaying}
          disabled={frameCount === 0}
        >
          {playing ? <PauseFilled size={20} /> : <PlayFilledAlt size={20} />}
        </IconButton>
      </Tooltip>
      <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
        {frameCount > 0 ? `${index + 1} / ${frameCount}` : "0 / 0"}
      </Typography>
      <Tooltip title="Playback speed">
        <Select
          size="small"
          variant="standard"
          value={fps}
          onChange={(event) => onFpsChange(Number(event.target.value))}
          inputProps={{ "aria-label": "Playback speed" }}
        >
          {FPS_OPTIONS.map((option) => (
            <MenuItem key={option} value={option}>
              {option} fps
            </MenuItem>
          ))}
        </Select>
      </Tooltip>
      <Tooltip title="Loop">
        <IconButton
          aria-label="Loop"
          aria-pressed={loop}
          color={loop ? "primary" : "default"}
          onClick={() => onLoopChange(!loop)}
        >
          <Repeat size={20} />
        </IconButton>
      </Tooltip>
      <Tooltip title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}>
        <IconButton
          aria-label={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
          onClick={onToggleFullscreen}
        >
          {isFullscreen ? <Minimize size={20} /> : <Maximize size={20} />}
        </IconButton>
      </Tooltip>
    </Stack>
  );
}

type TimelapsePlayerProps = {
  camera_identifier: string;
  frames: types.TimelapseFrame[];
  step: number | null;
  stream: types.TimelapseStream;
};

export function TimelapsePlayer({
  camera_identifier,
  frames,
  step,
  stream,
}: TimelapsePlayerProps) {
  const [active, setActive] = useState({ frames, stream });
  const [index, setIndex] = useState(0);
  // A frame's JPEG covers the video while it has nothing to show. It is not
  // updated while seeking, which would fetch a JPEG per step.
  const [stillIndex, setStillIndex] = useState<number | null>(0);
  const [fps, setFps] = useState(DEFAULT_FPS);
  const [loop, setLoop] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  // While a still is shown the video's time does not match the index
  const stillRef = useRef(true);
  const draggingRef = useRef(false);
  const scrubTimeout = useTimeout();
  const { isFullscreen, toggleFullscreen } = useFullscreen();
  const lastIndex = active.frames.length - 1;
  const streamFps = active.stream.fps;

  const showStill = useCallback((stillFrameIndex: number | null) => {
    stillRef.current = stillFrameIndex !== null;
    setStillIndex(stillFrameIndex);
  }, []);

  const { playing, buffering } = useVideoPlayback(videoRef, {
    onTimeUpdate: (time) => {
      // Pause updates while scrubbing
      if (stillRef.current || draggingRef.current) {
        return;
      }
      setIndex(Math.min(frameAt(time, streamFps), lastIndex));
    },
    onFrameShown: () => showStill(null),
  });
  usePlaybackRate(videoRef, fps / streamFps);

  // A range that ends now is refetched as frames are saved. Loading a new
  // playlist interrupts playback, so new frames are picked up while paused.
  if (!playing && frames !== active.frames) {
    const next = frameIndexAtOrAfter(
      frames,
      active.frames[index]?.timestamp ?? 0,
    );
    showStill(next);
    setActive({ frames, stream });
    setIndex(next);
  }

  const gaps = useMemo(
    () => findGaps(active.frames, step),
    [active.frames, step],
  );
  const playlist = useMemo(
    () =>
      buildTimelapsePlaylist(camera_identifier, active.frames, active.stream),
    [camera_identifier, active],
  );

  const { error, load } = useTimelapseHls(videoRef, playlist, () =>
    showStill(index),
  );

  const seek = useCallback(
    (i: number) => {
      setIndex(i);
      if (videoRef.current) {
        videoRef.current.currentTime = frameTime(i, streamFps);
      }
      // After setting currentTime, which media error recovery resumes from
      load(frameTime(i, streamFps));
    },
    [streamFps, load],
  );

  // Like a regular video, buffered frames are shown while dragging. Seeking to
  // unbuffered ones on every change would encode a segment per step.
  const scrub = (i: number) => {
    draggingRef.current = true;
    const video = videoRef.current;
    video?.pause();
    setIndex(i);
    scrubTimeout.clear();
    const time = frameTime(i, streamFps);
    if (video && isBuffered(video.buffered, time)) {
      video.currentTime = time;
      return;
    }
    scrubTimeout.start(() => seek(i), SCRUB_SEEK_DELAY_MS);
  };

  const endScrub = (i: number) => {
    scrubTimeout.clear();
    draggingRef.current = false;
    seek(i);
  };

  const togglePlaying = useCallback(() => {
    const video = videoRef.current;
    if (!video) {
      return;
    }
    if (playing) {
      video.pause();
      return;
    }
    if (index >= lastIndex) {
      seek(0);
    } else {
      load(frameTime(index, streamFps));
    }
    // Rejects when a pause interrupts it, which needs no handling
    video.play().catch(() => {});
  }, [playing, index, lastIndex, seek, load, streamFps]);

  const stillFrame = stillIndex === null ? null : active.frames[stillIndex];

  return (
    <Box
      ref={containerRef}
      data-testid="timelapse-player"
      sx={{
        display: "flex",
        flexDirection: "column",
        backgroundColor: "background.paper",
      }}
    >
      <VideoArea
        videoRef={videoRef}
        stream={active.stream}
        loop={loop}
        isFullscreen={isFullscreen}
        stillFrame={stillFrame}
        error={error}
        buffering={buffering}
        onClick={togglePlaying}
      />
      <FrameSlider
        frames={active.frames}
        index={index}
        gaps={gaps}
        onScrub={scrub}
        onScrubEnd={endScrub}
      />
      <PlayerControls
        playing={playing}
        index={index}
        frameCount={active.frames.length}
        fps={fps}
        loop={loop}
        isFullscreen={isFullscreen}
        onTogglePlaying={togglePlaying}
        onFpsChange={setFps}
        onLoopChange={setLoop}
        onToggleFullscreen={() =>
          toggleFullscreen(containerRef.current ?? undefined)
        }
      />
    </Box>
  );
}
