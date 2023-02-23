import Image from "@jy95/material-ui-image";
import { CardActions, CardMedia } from "@mui/material";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import { useCallback, useContext, useEffect, useRef, useState } from "react";
import { usePageVisibility } from "react-page-visibility";

import {
  CardActionButtonHref,
  CardActionButtonLink,
} from "components/CardActionButton";
import { ViseronContext } from "context/ViseronContext";
import useOnScreen from "hooks/UseOnScreen";
import { useCamera } from "lib/api/camera";
import queryClient from "lib/api/client";
import { subscribeStates } from "lib/commands";
import * as types from "lib/types";
import { SubscriptionUnsubscribe } from "lib/websockets";

interface CameraCardProps {
  camera: types.Camera;
}

const blankImage =
  "data:image/svg+xml;charset=utf8,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%3E%3C/svg%3E";

export default function CameraCard({ camera }: CameraCardProps) {
  const { connection } = useContext(ViseronContext);
  const theme = useTheme();
  const ref: any = useRef<HTMLDivElement>();
  const onScreen = useOnScreen<HTMLDivElement>(ref, "-1px");
  const isVisible = usePageVisibility();
  const [initialRender, setInitialRender] = useState(true);
  const cameraQuery = useCamera({ camera_identifier: camera.identifier });

  const generateSnapshotURL = useCallback(
    (width = null) =>
      `/api/v1/camera/${camera.identifier}/snapshot?rand=${(Math.random() + 1)
        .toString(36)
        .substring(7)}${width ? `&width=${width}` : ""}&access_token=${
        cameraQuery.data?.access_token
      }`,
    [camera.identifier, cameraQuery.data?.access_token]
  );
  const [snapshotURL, setSnapshotURL] = useState({
    // Show blank image on start
    url: blankImage,
    disableSpinner: false,
    disableTransition: false,
    loading: true,
  });
  const updateSnapshot = useRef<NodeJS.Timer | null>();
  const updateImage = useCallback(() => {
    setSnapshotURL((prevSnapshotURL) => {
      if (cameraQuery.isLoading) {
        // Dont load new image if we are loading token
        console.log("Not loading new image because we are loading token");
        return prevSnapshotURL;
      }
      if (prevSnapshotURL.loading) {
        // Dont load new image if we are still loading
        return prevSnapshotURL;
      }
      if (initialRender) {
        // Make sure we show the spinner on the first image fetched.
        setInitialRender(false);
        return {
          url: generateSnapshotURL(
            ref.current ? ref.current.offsetWidth : null
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
  }, [cameraQuery.isLoading, generateSnapshotURL, initialRender]);

  useEffect(() => {
    // If element is on screen and browser is visible, start interval to fetch images
    if (onScreen && isVisible) {
      updateImage();
      updateSnapshot.current = setInterval(() => {
        updateImage();
      }, 10000);
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
  }, [updateImage, isVisible, onScreen]);

  useEffect(() => {
    const stateChanged = async (
      _stateChangedEvent: types.StateChangedEvent
    ) => {
      queryClient.invalidateQueries(["camera", camera.identifier]);
    };

    let unsub: SubscriptionUnsubscribe;
    const subcscribeEntities = async () => {
      if (connection) {
        unsub = await subscribeStates(
          connection,
          stateChanged,
          `sensor.${camera.identifier}_access_token`
        );
      }
    };
    subcscribeEntities();
    return () => {
      const unsubcscribeEntities = async () => {
        await unsub();
      };
      unsubcscribeEntities();
    };
  }, [camera, connection]);

  return (
    <Card
      ref={ref}
      variant="outlined"
      sx={{
        // Vertically space items evenly to accommodate different aspect ratios
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
      }}
    >
      <CardContent>
        <Typography variant="h5" align="center">
          {camera.name}
        </Typography>
      </CardContent>
      <CardMedia>
        {/* 'alt=""' in combination with textIndent is a neat trick to hide the broken image icon */}
        <Image
          alt=""
          imageStyle={{ textIndent: "-10000px" }}
          src={snapshotURL.url}
          disableSpinner={snapshotURL.disableSpinner}
          disableTransition={snapshotURL.disableTransition}
          animationDuration={1000}
          aspectRatio={camera.width / camera.height}
          color={theme.palette.background.default}
          onLoad={() => {
            setSnapshotURL((prevSnapshotURL) => ({
              ...prevSnapshotURL,
              disableSpinner: true,
              disableTransition: true,
              loading: false,
            }));
          }}
          errorIcon={Image.defaultProps!.loading}
          onError={() => {
            setSnapshotURL((prevSnapshotURL) => ({
              ...prevSnapshotURL,
              disableSpinner: false,
              disableTransition: false,
              loading: false,
            }));
          }}
        />
      </CardMedia>
      <CardActions>
        <CardActionButtonLink
          title="Recordings"
          target={`/recordings/${camera.identifier}`}
        />
        <CardActionButtonHref
          title="Live View"
          target={`/${camera.identifier}/mjpeg-stream`}
        />
      </CardActions>
    </Card>
  );
}
