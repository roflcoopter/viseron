import Image from "@jy95/material-ui-image";
import {
  IntrusionPrevention,
  VideoChat,
  Demo,
  Roadmap,
  VideoOff,
} from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardActionArea from "@mui/material/CardActionArea";
import CardActions from "@mui/material/CardActions";
import CardContent from "@mui/material/CardContent";
import CardMedia from "@mui/material/CardMedia";
import CircularProgress from "@mui/material/CircularProgress";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import { useCallback, useContext, useEffect, useRef, useState } from "react";
import { usePageVisibility } from "react-page-visibility";
import { Link } from "react-router-dom";

import { CameraNameOverlay } from "components/camera/CameraNameOverlay";
import { CameraUptime } from "components/camera/CameraUptime";
import { FailedCameraCard } from "components/camera/FailedCameraCard";
import { ViseronContext } from "context/ViseronContext";
import { useFirstRender } from "hooks/UseFirstRender";
import useOnScreen from "hooks/UseOnScreen";
import { useCamera } from "lib/api/camera";
import * as types from "lib/types";

type OnClick = (
  event: React.MouseEvent<HTMLButtonElement, MouseEvent>,
  camera: types.Camera,
) => void;

type FailedOnClick = (
  event: React.MouseEvent<HTMLButtonElement, MouseEvent>,
  camera: types.FailedCamera,
) => void;

interface SuccessCameraCardProps {
  camera: types.Camera;
  buttons?: boolean;
  compact?: boolean;
  onClick?: OnClick;
  border?: string;
}

interface CameraCardProps {
  camera_identifier: string;
  buttons?: boolean;
  compact?: boolean;
  onClick?: OnClick | FailedOnClick;
  border?: string;
}

const blankImage =
  "data:image/svg+xml;charset=utf8,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%3E%3C/svg%3E";

function SuccessCameraCard({
  camera,
  buttons = true,
  compact = false,
  onClick,
  border,
}: SuccessCameraCardProps) {
  const { connected } = useContext(ViseronContext);
  const theme = useTheme();
  const ref: any = useRef<HTMLDivElement>(undefined);
  const onScreen = useOnScreen<HTMLDivElement>(ref);
  const isVisible = usePageVisibility();
  const firstRender = useFirstRender();

  const generateSnapshotURL = useCallback(
    (width = null) =>
      `/api/v1/camera/${camera.identifier}/snapshot?rand=${(Math.random() + 1)
        .toString(36)
        .substring(7)}${width ? `&width=${Math.trunc(width)}` : ""}`,
    [camera.identifier],
  );
  const [snapshotURL, setSnapshotURL] = useState({
    // Show blank image on start
    url: blankImage,
    disableSpinner: false,
    disableTransition: false,
    loading: true,
  });
  const updateSnapshot = useRef<NodeJS.Timeout | null>(undefined);
  const updateImage = useCallback(() => {
    setSnapshotURL((prevSnapshotURL) => {
      if (prevSnapshotURL.loading && !firstRender) {
        // Dont load new image if we are still loading
        return prevSnapshotURL;
      }
      if (firstRender) {
        // Make sure we show the spinner on the first image fetched.
        return {
          url: generateSnapshotURL(
            ref.current ? ref.current.offsetWidth : null,
          ),
          disableSpinner: false,
          disableTransition: false,
          loading: true,
        };
      }
      return {
        ...prevSnapshotURL,
        url: generateSnapshotURL(ref.current ? ref.current.offsetWidth : null),
        loading: true,
      };
    });
  }, [firstRender, generateSnapshotURL]);

  useEffect(() => {
    // If element is on screen and browser is visible, start interval to fetch images
    if (onScreen && isVisible && connected && camera.still_image.available) {
      updateImage();
      updateSnapshot.current = setInterval(
        () => {
          updateImage();
        },
        camera.still_image.refresh_interval
          ? camera.still_image.refresh_interval * 1000
          : 10000,
      );
      // If element is hidden or browser loses focus, stop updating images
    } else if (updateSnapshot.current) {
      clearInterval(updateSnapshot.current);
    }
    return () => {
      // Stop updating on unmount
      if (updateSnapshot.current) {
        clearInterval(updateSnapshot.current);
      }
    };
  }, [
    updateImage,
    isVisible,
    onScreen,
    connected,
    camera.still_image.available,
    camera.still_image.refresh_interval,
  ]);

  return (
    <div
      ref={ref}
      style={{
        height: "100%",
      }}
    >
      <Card
        variant="outlined"
        sx={[
          {
            // Vertically space items evenly to accommodate different aspect ratios
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            height: "100%",
          },
          compact ? { position: "relative" } : null,
          border ? { border } : null,
        ]}
      >
        {compact ? (
          <CameraNameOverlay camera_identifier={camera.identifier} />
        ) : (
          <CardContent>
            <Typography variant="h5" align="center">
              {camera.name}
            </Typography>
          </CardContent>
        )}
        <CardActionArea
          onClick={
            onClick ? (event) => (onClick as OnClick)(event, camera) : undefined
          }
          sx={onClick ? null : { pointerEvents: "none" }}
        >
          <CardMedia>
            {!camera.connected ? (
              <Box
                sx={{
                  aspectRatio: camera.still_image.width / camera.still_image.height,
                  backgroundColor: theme.palette.background.default,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  minHeight: 200,
                }}
              >
                <VideoOff 
                  size={48} 
                  style={{ 
                    color: theme.palette.text.secondary,
                    opacity: 0.5 
                  }} 
                />
              </Box>
            ) : (
              <Image
                src={snapshotURL.url}
                disableSpinner={snapshotURL.disableSpinner}
                disableTransition={snapshotURL.disableTransition}
                animationDuration={1000}
                aspectRatio={camera.still_image.width / camera.still_image.height}
                color={theme.palette.background.default}
                onLoad={() => {
                  setSnapshotURL((prevSnapshotURL) => ({
                    ...prevSnapshotURL,
                    disableSpinner: true,
                    disableTransition: true,
                    loading: false,
                  }));
                }}
                errorIcon={
                  camera.still_image.available ? <CircularProgress enableTrackSlot/> : null
                }
                onError={() => {
                  setSnapshotURL((prevSnapshotURL) => ({
                    ...prevSnapshotURL,
                    disableSpinner: false,
                    disableTransition: false,
                    loading: false,
                  }));
                }}
              />
            )}
          </CardMedia>
        </CardActionArea>
        {buttons && (
          <CardActions>
            <Stack direction="row" spacing={1} sx={{ width: "100%", justifyContent: "space-between", alignItems: "center" }}>
              <Tooltip title="Uptime Status">
                <div style={{ cursor: "pointer" }}>
                  <CameraUptime
                    cameraIdentifier={camera.identifier}
                    isConnected={camera.connected}
                    compact
                  />
                </div>
              </Tooltip>
              <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                <Tooltip title="Events">
                  <IconButton
                    component={Link}
                    to={`/events?camera=${camera.identifier}&tab=events`}
                  >
                    <IntrusionPrevention size={20}/>
                  </IconButton>
                </Tooltip>
                <Tooltip title="Timeline">
                  <IconButton
                    component={Link}
                    to={`/events?camera=${camera.identifier}&tab=timeline`}
                  >
                    <Roadmap size={20}/>
                  </IconButton>
                </Tooltip>
                <Tooltip title="Recordings">
                  <IconButton
                    component={Link}
                    to={`/recordings/${camera.identifier}`}
                  >
                    <Demo size={20}/>
                  </IconButton>
                </Tooltip>
                <Tooltip title="Live View">
                  <IconButton
                    component={Link}
                    to={`/live?camera=${camera.identifier}`}
                  >
                    <VideoChat size={20}/>
                  </IconButton>
                </Tooltip>
              </Stack>
            </Stack>
          </CardActions>
        )}
      </Card>
    </div>
  );
}
export function CameraCard({
  camera_identifier,
  buttons = true,
  compact = false,
  onClick,
  border,
}: CameraCardProps) {
  const { connected } = useContext(ViseronContext);
  const cameraQuery = useCamera(camera_identifier, true, {
    enabled: connected,
  });
  if (!cameraQuery.data) {
    return null;
  }
  if (cameraQuery.data.failed) {
    return (
      <FailedCameraCard
        failedCamera={cameraQuery.data}
        compact={compact}
        onClick={(onClick as FailedOnClick) || undefined}
      />
    );
  }
  return (
    <SuccessCameraCard
      camera={cameraQuery.data}
      buttons={buttons}
      compact={compact}
      onClick={onClick as OnClick | undefined}
      border={border}
    />
  );
}
