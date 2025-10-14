import { useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import { useCallback, useEffect, useState } from "react";

import { playerCardSmMaxHeight } from "components/events/utils";
import { useResizeObserver } from "hooks/UseResizeObserver";
import * as types from "lib/types";

export type GridLayout = {
  columns: number;
  rows: number;
};

// Dont fully understand why we need to subtract 4 from the height
// to keep the players from overflowing the paper
const getContainerHeight = (
  containerRef: React.RefObject<HTMLDivElement | null>,
  smBreakpoint: boolean,
) =>
  smBreakpoint
    ? containerRef.current?.clientHeight || 0
    : playerCardSmMaxHeight() -
      ((containerRef.current?.offsetHeight || 0) -
        (containerRef.current?.clientHeight || 0)) -
      4;

const calculateCellDimensions = (
  containerRef: React.RefObject<HTMLDivElement | null>,
  camera: types.Camera | types.FailedCamera,
  gridLayout: GridLayout,
  smBreakpoint: boolean,
) => {
  const containerWidth = containerRef.current?.clientWidth || 0;
  const containerHeight = getContainerHeight(containerRef, smBreakpoint);
  const cellWidth = containerWidth / gridLayout.columns;
  const cellHeight = containerHeight / gridLayout.rows;
  const cameraAspectRatio = camera.mainstream.width / camera.mainstream.height;
  const cellAspectRatio = cellWidth / cellHeight;

  if (cameraAspectRatio > cellAspectRatio) {
    // Video is wider than the cell, fit to width
    const width = cellWidth;
    const height = cellWidth / cameraAspectRatio;
    return { width, height };
  }
  // Video is taller than the cell, fit to height
  const height = Math.floor(cellHeight);
  const width = Math.floor(cellHeight * cameraAspectRatio);
  return { width, height };
};

const calculateLayout = (
  containerRef: React.RefObject<HTMLDivElement | null>,
  cameras: types.CamerasOrFailedCameras,
  smBreakpoint: boolean,
) => {
  if (!containerRef.current) return { columns: 1, rows: 1 };

  const containerWidth = containerRef.current.clientWidth;
  const containerHeight = getContainerHeight(containerRef, smBreakpoint);
  const camerasLength = Object.keys(cameras).length;

  let bestLayout = { columns: 1, rows: 1 };
  let maxMinDimension = 0;

  for (let columns = 1; columns <= camerasLength; columns++) {
    const rows = Math.ceil(camerasLength / columns);
    const cellWidth = containerWidth / columns;
    const cellHeight = containerHeight / rows;

    // Calculate the minimum dimension (width or height) of any camera in this layout
    let minDimension = Math.min(cellWidth, cellHeight);

    // Adjust for aspect ratio
    Object.values(cameras).forEach((camera) => {
      const aspectRatio = camera.mainstream.width / camera.mainstream.height;
      const adjustedWidth = Math.min(cellWidth, cellHeight * aspectRatio);
      const adjustedHeight = Math.min(cellHeight, cellWidth / aspectRatio);
      minDimension = Math.min(minDimension, adjustedWidth, adjustedHeight);
    });

    // If this layout results in larger minimum dimensions, it's our new best layout
    if (minDimension > maxMinDimension) {
      maxMinDimension = minDimension;
      bestLayout = { columns, rows };
    }

    // If adding more columns would make cells smaller than they need to be, stop here
    if (cellWidth < minDimension) {
      break;
    }
  }

  return bestLayout;
};

export const useGridLayout = (
  containerRef: React.RefObject<HTMLDivElement | null>,
  cameras: types.CamerasOrFailedCameras,
  setPlayerItemsSize: () => void,
  overrideSmBreakpoint?: boolean | undefined,
) => {
  const theme = useTheme();
  const smBreakpoint = useMediaQuery(theme.breakpoints.up("sm"));
  const [gridLayout, setGridLayout] = useState<{
    columns: number;
    rows: number;
  }>({ columns: 1, rows: 1 });

  const handleResize = useCallback(() => {
    const layout = calculateLayout(
      containerRef,
      cameras,
      overrideSmBreakpoint === undefined ? smBreakpoint : overrideSmBreakpoint,
    );
    if (
      layout.columns !== gridLayout.columns ||
      layout.rows !== gridLayout.rows
    ) {
      setGridLayout(layout);
    }
    setPlayerItemsSize();
  }, [
    containerRef,
    cameras,
    overrideSmBreakpoint,
    smBreakpoint,
    gridLayout.columns,
    gridLayout.rows,
    setPlayerItemsSize,
  ]);

  // Observe both the containerRef and window resize to update the layout
  useResizeObserver(containerRef, handleResize);
  useEffect(() => {
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [handleResize]);

  return gridLayout;
};

export const setPlayerSize = (
  containerRef: React.RefObject<HTMLDivElement | null>,
  boxRef: React.RefObject<HTMLDivElement | null>,
  camera: types.Camera | types.FailedCamera,
  gridLayout: GridLayout,
  smBreakpoint: boolean,
) => {
  if (containerRef.current && boxRef.current) {
    const { width, height } = calculateCellDimensions(
      containerRef,
      camera,
      gridLayout,
      smBreakpoint,
    );
    boxRef.current.style.width = `${width}px`;
    boxRef.current.style.height = `${height}px`;
  }
};
