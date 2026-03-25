import Image from "@jy95/material-ui-image";
import { Card, CardContent, useTheme } from "@mui/material";
import { useContext, useEffect, useRef } from "react";
import { usePageVisibility } from "react-page-visibility";

import { ViseronContext } from "context/ViseronContext";
import useOnScreen from "hooks/UseOnScreen";

import { renderOverlay } from "./TuneOverlay";

interface Camera {
  identifier: string;
  still_image: {
    width: number;
    height: number;
    available: boolean;
    refresh_interval?: number;
  };
}

interface TuneSnapshotProps {
  camera: Camera;
  snapshotURL: {
    url: string;
    loading: boolean;
    disableSpinner: boolean;
    disableTransition: boolean;
  };
  isDrawingMode: boolean;
  selectedComponentData: any;
  selectedZoneIndex: number | null;
  selectedMaskIndex: number | null;
  selectedOSDTextIndex: number | null;
  selectedVideoTransformIndex: number | null;
  drawingType: "zone" | "mask" | null;
  drawingPoints: Array<{ x: number; y: number }>;
  onSnapshotLoad: () => void;
  onSnapshotError: () => void;
  onImageClick: (event: React.MouseEvent<HTMLDivElement>) => void;
  onUpdateSnapshot: () => void;
  onPointDrag?: (
    type: "zone" | "mask",
    itemIndex: number,
    pointIndex: number,
    newX: number,
    newY: number,
  ) => void;
  onPolygonDrag?: (
    type: "zone" | "mask",
    itemIndex: number,
    deltaX: number,
    deltaY: number,
    imageWidth: number,
    imageHeight: number,
  ) => void;
}

export function TuneSnapshot({
  camera,
  snapshotURL,
  isDrawingMode,
  selectedComponentData,
  selectedZoneIndex,
  selectedMaskIndex,
  selectedOSDTextIndex,
  selectedVideoTransformIndex,
  drawingType,
  drawingPoints,
  onSnapshotLoad,
  onSnapshotError,
  onImageClick,
  onUpdateSnapshot,
  onPointDrag,
  onPolygonDrag,
}: TuneSnapshotProps) {
  const theme = useTheme();
  const { connected } = useContext(ViseronContext);
  const ref: any = useRef<HTMLDivElement>(undefined);
  const onScreen = useOnScreen<HTMLDivElement>(ref);
  const isVisible = usePageVisibility();
  const updateSnapshot = useRef<NodeJS.Timeout | null>(undefined);

  // Get active video transform
  const activeVideoTransform =
    selectedVideoTransformIndex !== null &&
    selectedComponentData?.video_transforms?.[selectedVideoTransformIndex]
      ? selectedComponentData.video_transforms[selectedVideoTransformIndex]
      : null;

  // Calculate CSS transform based on active video transform
  const getImageTransform = () => {
    if (!activeVideoTransform) return "none";

    switch (activeVideoTransform.transform) {
      case "hflip":
        return "scaleX(-1)";
      case "vflip":
        return "scaleY(-1)";
      case "rotate180":
        return "rotate(180deg)";
      default:
        return "none";
    }
  };

  useEffect(() => {
    // If element is on screen and browser is visible, start interval to fetch images
    if (onScreen && isVisible && connected && camera.still_image.available) {
      onUpdateSnapshot();
      updateSnapshot.current = setInterval(
        () => {
          onUpdateSnapshot();
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
    onUpdateSnapshot,
    isVisible,
    onScreen,
    connected,
    camera.still_image.available,
    camera.still_image.refresh_interval,
  ]);

  return (
    <Card
      ref={ref}
      variant="outlined"
      sx={{
        height: { md: "72.5vh" },
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        overflow: "hidden",
      }}
    >
      <CardContent
        sx={{
          flexGrow: 1,
          p: 0,
          "&:last-child": { pb: 0 },
          position: "relative",
          cursor: isDrawingMode ? "crosshair" : "default",
        }}
        onClick={onImageClick}
      >
        <Image
          src={snapshotURL.url}
          disableSpinner={snapshotURL.disableSpinner}
          disableTransition={snapshotURL.disableTransition}
          animationDuration={1000}
          aspectRatio={camera.still_image.width / camera.still_image.height}
          color={theme.palette.background.default}
          onLoad={onSnapshotLoad}
          onError={onSnapshotError}
          style={{
            transform: getImageTransform(),
            transition: "transform 0.3s ease",
          }}
        />
        {renderOverlay({
          camera,
          selectedComponentData,
          selectedZoneIndex,
          selectedMaskIndex,
          selectedOSDTextIndex,
          selectedVideoTransformIndex,
          isDrawingMode,
          drawingType,
          drawingPoints,
          onPointDrag,
          onPolygonDrag,
        })}
      </CardContent>
    </Card>
  );
}
