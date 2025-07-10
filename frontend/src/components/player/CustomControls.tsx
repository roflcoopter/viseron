import CircleIcon from "@mui/icons-material/Circle";
import Forward10Icon from "@mui/icons-material/Forward10";
import FullscreenIcon from "@mui/icons-material/Fullscreen";
import FullscreenExitIcon from "@mui/icons-material/FullscreenExit";
import PauseIcon from "@mui/icons-material/Pause";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import Replay10Icon from "@mui/icons-material/Replay10";
import SpeedIcon from "@mui/icons-material/Speed";
import VolumeOffIcon from "@mui/icons-material/VolumeOff";
import VolumeUpIcon from "@mui/icons-material/VolumeUp";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Fab from "@mui/material/Fab";
import Fade from "@mui/material/Fade";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Slider from "@mui/material/Slider";
import Typography from "@mui/material/Typography";
import { SxProps, Theme } from "@mui/material/styles";
import React, { useCallback, useEffect, useRef, useState } from "react";
import screenfull from "screenfull";

import { isTouchDevice } from "lib/helpers";

const ZINDEX = 3;

interface CustomFabProps {
  onClick: (event: React.MouseEvent<HTMLButtonElement>) => void;
  size?: "small" | "medium" | "large";
  children: React.ReactNode;
}
export const CustomFab = ({
  onClick,
  size = "small",
  children,
}: CustomFabProps) => (
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

const iconStyles: SxProps<Theme> = {
  width: "12px",
  height: "12px",
  marginRight: 1,
};

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
  extraButtons?: React.ReactNode;
}

export const CustomControls: React.FC<CustomControlsProps> = ({
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
  extraButtons,
}) => {
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
            <CustomFab onClick={onJumpBackward}>
              <Replay10Icon />
            </CustomFab>
          )}
          {onPlayPause && (
            <CustomFab onClick={onPlayPause} size="medium">
              {isPlaying ? <PauseIcon /> : <PlayArrowIcon />}
            </CustomFab>
          )}
          {onJumpForward && (
            <CustomFab onClick={onJumpForward}>
              <Forward10Icon />
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
              <CircleIcon htmlColor={isLive ? "red" : "gray"} sx={iconStyles} />
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
                  <CustomFab onClick={onMuteToggle}>
                    {isMuted ? <VolumeOffIcon /> : <VolumeUpIcon />}
                  </CustomFab>
                )}
              </Box>
            )}
            {onPlaybackSpeedChange && (
              <>
                <CustomFab onClick={handleSpeedClick}>
                  <SpeedIcon />
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
            {onFullscreenToggle && screenfull.isEnabled && (
              <CustomFab onClick={onFullscreenToggle}>
                {isFullscreen ? <FullscreenExitIcon /> : <FullscreenIcon />}
              </CustomFab>
            )}
          </Box>
        </Box>
      </Box>
    </Fade>
  );
};
