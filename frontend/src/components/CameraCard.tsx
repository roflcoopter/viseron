import Image from "@jy95/material-ui-image";
import { CardActionArea, CardActions } from "@mui/material";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import { useCallback, useEffect, useRef, useState } from "react";
import { usePageVisibility } from "react-page-visibility";

import {
  CardActionButtonHref,
  CardActionButtonLink,
} from "components/CardActionButton";
import useOnScreen from "hooks/UseOnScreen";
import * as types from "lib/types";

interface CameraCardProps {
  camera: types.Camera;
}

const blankImage =
  "data:image/svg+xml;charset=utf8,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%3E%3C/svg%3E";

export default function CameraCard({ camera }: CameraCardProps) {
  const theme = useTheme();
  const ref: any = useRef<HTMLDivElement>();
  const onScreen = useOnScreen<HTMLDivElement>(ref, "-1px");
  const isVisible = usePageVisibility();
  const [initialRender, setInitialRender] = useState(true);

  const generateSnapshotURL = useCallback(
    (width = null) =>
      `/api/v1/camera/${camera.identifier}/snapshot?rand=${(Math.random() + 1)
        .toString(36)
        .substring(7)}${width ? `&width=${width}` : ""}`,
    [camera.identifier]
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
  }, [generateSnapshotURL, initialRender]);

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
  }, [updateImage, isVisible, onScreen, generateSnapshotURL]);

  return (
    <Card ref={ref} variant="outlined">
      <CardContent>
        <Typography variant="h5" align="center">
          {camera.name}
        </Typography>
      </CardContent>
      <CardActionArea>
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
      </CardActionArea>
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
