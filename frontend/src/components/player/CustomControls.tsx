import {
  Rewind_10 as Rewind10,
  Forward_10 as Forward10,
  Pause,
  Play,
  VolumeMute,
  VolumeUp,
  MeterAlt,
  Launch,
  PopIn,
  CircleFill,
  ShrinkScreen,
} from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Fab from "@mui/material/Fab";
import Fade from "@mui/material/Fade";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Slider from "@mui/material/Slider";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import React, { useCallback, useEffect, useRef, useState } from "react";
import screenfull from "screenfull";

import { useFullscreen } from "context/FullscreenContext";
import { isTouchDevice } from "lib/helpers";

const ZINDEX = 900;

interface CustomFabProps {
  onClick: (event: React.MouseEvent<HTMLButtonElement>) => void;
  size?: "small" | "medium" | "large";
  children: React.ReactNode;
  title?: string;
  isFullscreen?: boolean;
}
export function CustomFab({
  onClick,
  size = "small",
  children,
  title,
  isFullscreen = false,
}: CustomFabProps) {
  const { isFullscreen: isContainerFullscreen } = useFullscreen();

  const fab = (
    <Fab
      onClick={onClick}
      onTouchStart={(e) => e.stopPropagation()}
      size={size}
      color="primary"
      sx={{ margin: 0.25, zIndex: ZINDEX }}
    >
      {children}
    </Fab>
  );

  // Determine z-index based on fullscreen state or container fullscreen
  const tooltipZIndex = isFullscreen || isContainerFullscreen ? 9001 : 999;

  return title ? (
    <Tooltip 
      title={title}
      arrow={false}
      PopperProps={{
        style: { zIndex: tooltipZIndex }
      }}
    >
      {fab}
    </Tooltip>
  ) : fab;
}

interface CustomControlsProps {
  isPlaying?: boolean;
  onPlayPause?: () => void;
  onJumpBackward?: () => void;
  onJumpForward?: () => void;
  isVisible?: boolean;
  isLive?: boolean;
  onLiveClick?: () => void;
  onVolumeChange?: (event: Event, volume: number | number[]) => void;
  isMuted?: boolean;
  onMuteToggle?: () => void;
  onPlaybackSpeedChange?: (speed: number) => void;
  playbackSpeed?: number;
  isFullscreen?: boolean;
  onFullscreenToggle?: () => void;
  onPictureInPictureToggle?: () => void;
  isPictureInPictureSupported?: boolean;
  extraButtons?: React.ReactNode;
}

export function CustomControls({
  isPlaying = false,
  onPlayPause,
  onJumpBackward,
  onJumpForward,
  isVisible = false,
  isLive = false,
  onLiveClick,
  onVolumeChange,
  isMuted = false,
  onMuteToggle,
  onPlaybackSpeedChange,
  playbackSpeed = 1,
  isFullscreen = false,
  onFullscreenToggle,
  onPictureInPictureToggle,
  isPictureInPictureSupported = false,
  extraButtons,
}: CustomControlsProps) {
  const [isVolumeSliderVisible, setIsVolumeSliderVisible] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const volumeControlRef = useRef<HTMLDivElement>(null);

  const handleVolumeControlMouseEnter = useCallback(() => {
    if (!isDragging) {
      setIsVolumeSliderVisible(true);
    }
  }, [isDragging]);

  const handleVolumeControlMouseLeave = useCallback(() => {
    if (!isDragging) {
      setIsVolumeSliderVisible(false);
    }
  }, [isDragging]);

  const handleMouseDown = useCallback(() => {
    setIsDragging(true);
  }, []);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleSpeedClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handlePlaybackSpeedChange = (speed: number) => {
    if (onPlaybackSpeedChange) {
      onPlaybackSpeedChange(speed);
    }
    handleClose();
  };

  useEffect(() => {
    const handleGlobalMouseUp = (e: MouseEvent) => {
      if (isDragging) {
        setIsDragging(false);
        if (!volumeControlRef.current?.contains(e.target as Node)) {
          setIsVolumeSliderVisible(false);
        }
      }
    };

    document.addEventListener("mouseup", handleGlobalMouseUp);
    return () => {
      document.removeEventListener("mouseup", handleGlobalMouseUp);
    };
  }, [isDragging]);

  return (
    <Fade in={isVisible || Boolean(anchorEl)} timeout={300}>
      <Box
        sx={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          zIndex: ZINDEX,
        }}
      >
        {/* Center controls */}
        <Box display="flex" justifyContent="center" alignItems="center">
          {onJumpBackward && (
            <CustomFab onClick={onJumpBackward} title="Rewind 10 seconds" isFullscreen={isFullscreen}>
              <Rewind10 size={20}/>
            </CustomFab>
          )}
          {onPlayPause && (
            <CustomFab onClick={onPlayPause} size="medium" title={isPlaying ? "Pause" : "Play"} isFullscreen={isFullscreen}>
              {isPlaying ? <Pause size={20}/> : <Play size={20}/>}
            </CustomFab>
          )}
          {onJumpForward && (
            <CustomFab onClick={onJumpForward} title="Forward 10 seconds" isFullscreen={isFullscreen}>
              <Forward10 size={20}/>
            </CustomFab>
          )}
        </Box>

        {/* Bottom controls */}
        <Box
          sx={{
            position: "absolute",
            bottom: 5,
            left: 5,
            right: 5,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          {/* LIVE button */}
          {onLiveClick ? (
            <Button
              onClick={onLiveClick}
              onTouchStart={(e) => e.stopPropagation()}
              variant="contained"
              size="small"
              sx={{ margin: 0.25 }}
            >
              <CircleFill fill={isLive ? "red" : "gray"} size={12} style={{ marginRight: 8 }} />
              <Typography variant="button">LIVE</Typography>
            </Button>
          ) : (
            // Empty div so that 'space-between' works
            <div />
          )}

          {/* Right-aligned controls */}
          <Box display="flex" alignItems="center">
            {(onVolumeChange || onMuteToggle) && (
              <Box
                ref={volumeControlRef}
                sx={{
                  position: "relative",
                  display: "flex",
                  alignItems: "center",
                }}
                onMouseEnter={handleVolumeControlMouseEnter}
                onMouseLeave={handleVolumeControlMouseLeave}
              >
                {onVolumeChange && !isTouchDevice() && (
                  <Box
                    sx={(theme) => ({
                      position: "absolute",
                      right: "50%",
                      top: "50%",
                      transform: "translateY(-50%)",
                      height: 35,
                      width: isVolumeSliderVisible || isDragging ? 150 : 0,
                      visibility:
                        isVolumeSliderVisible || isDragging
                          ? "visible"
                          : "hidden",
                      bgcolor: "background.paper",
                      boxShadow: 1,
                      border: `1px solid ${
                        theme.palette.mode === "dark"
                          ? theme.palette.primary[900]
                          : theme.palette.primary[200]
                      }`,
                      borderTopLeftRadius: 20,
                      borderBottomLeftRadius: 20,
                      overflow: "hidden",
                      transition: "width 0.2s ease-in-out, visibility 0.2s",
                      display: "flex",
                      justifyContent: "center",
                      alignItems: "center",
                      pr: 3,
                    })}
                  >
                    <Slider
                      defaultValue={100}
                      orientation="horizontal"
                      onChange={onVolumeChange}
                      onMouseDown={handleMouseDown}
                      onMouseUp={handleMouseUp}
                      aria-labelledby="horizontal-volume-slider"
                      sx={{
                        width: "80%",
                        "& .MuiSlider-thumb": {
                          transition: "none",
                        },
                      }}
                      min={0}
                      max={100}
                    />
                  </Box>
                )}
                {onMuteToggle && (
                  <CustomFab onClick={onMuteToggle} title={isMuted ? "Unmute" : "Mute"} isFullscreen={isFullscreen}>
                    {isMuted ? <VolumeMute size={20}/> : <VolumeUp size={20}/>}
                  </CustomFab>
                )}
              </Box>
            )}
            {onPlaybackSpeedChange && (
              <>
                <CustomFab onClick={handleSpeedClick} title="Playback speed" isFullscreen={isFullscreen}>
                  <MeterAlt size={20}/>
                </CustomFab>
                <Menu
                  anchorEl={anchorEl}
                  open={Boolean(anchorEl)}
                  onClose={handleClose}
                  onTouchStart={(e) => e.stopPropagation()}
                >
                  <MenuItem
                    onClick={() => handlePlaybackSpeedChange(0.5)}
                    onTouchStart={(e) => e.stopPropagation()}
                    selected={playbackSpeed === 0.5}
                  >
                    0.5x
                  </MenuItem>
                  <MenuItem
                    onClick={() => handlePlaybackSpeedChange(1)}
                    onTouchStart={(e) => e.stopPropagation()}
                    selected={playbackSpeed === 1}
                  >
                    1x
                  </MenuItem>
                  <MenuItem
                    onClick={() => handlePlaybackSpeedChange(2)}
                    onTouchStart={(e) => e.stopPropagation()}
                    selected={playbackSpeed === 2}
                  >
                    2x
                  </MenuItem>
                  <MenuItem
                    onClick={() => handlePlaybackSpeedChange(5)}
                    onTouchStart={(e) => e.stopPropagation()}
                    selected={playbackSpeed === 5}
                  >
                    5x
                  </MenuItem>
                  <MenuItem
                    onClick={() => handlePlaybackSpeedChange(10)}
                    onTouchStart={(e) => e.stopPropagation()}
                    selected={playbackSpeed === 10}
                  >
                    10x
                  </MenuItem>
                </Menu>
              </>
            )}
            {extraButtons}
            {onPictureInPictureToggle && isPictureInPictureSupported && (
              <CustomFab onClick={onPictureInPictureToggle} title="Picture in Picture" isFullscreen={isFullscreen}>
                <ShrinkScreen size={20}/>
              </CustomFab>
            )}
            {onFullscreenToggle && screenfull.isEnabled && (
              <CustomFab onClick={onFullscreenToggle} title={isFullscreen ? "Exit fullscreen" : "Fullscreen"} isFullscreen={isFullscreen}>
                {isFullscreen ? <PopIn size={20}/> : <Launch size={20}/>}
              </CustomFab>
            )}
          </Box>
        </Box>
      </Box>
    </Fade>
  );
}
