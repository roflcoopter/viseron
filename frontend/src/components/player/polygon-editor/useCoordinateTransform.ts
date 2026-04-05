import { useCallback, useEffect, useState } from "react";

import { CoordinateTransform, Point } from "./types";

/**
 * Computes coordinate transform between camera-resolution coordinates
 * and display coordinates, accounting for object-fit: contain letterboxing.
 */
export function useCoordinateTransform(
  containerRef: React.RefObject<HTMLElement | null>,
  cameraWidth: number,
  cameraHeight: number,
): CoordinateTransform {
  const [transform, setTransform] = useState<CoordinateTransform>({
    toDisplay: (p: Point) => p,
    toCamera: (dx: number, dy: number) => ({ x: dx, y: dy }),
    scale: 1,
    offsetX: 0,
    offsetY: 0,
  });

  const calculate = useCallback(() => {
    const container = containerRef.current;
    if (!container || !cameraWidth || !cameraHeight) return;

    const cw = container.clientWidth;
    const ch = container.clientHeight;

    const scale = Math.min(cw / cameraWidth, ch / cameraHeight);
    const displayWidth = cameraWidth * scale;
    const displayHeight = cameraHeight * scale;
    const offsetX = (cw - displayWidth) / 2;
    const offsetY = (ch - displayHeight) / 2;

    setTransform({
      scale,
      offsetX,
      offsetY,
      toDisplay: (p: Point) => ({
        x: p.x * scale + offsetX,
        y: p.y * scale + offsetY,
      }),
      toCamera: (dx: number, dy: number) => ({
        x: Math.round(
          Math.max(0, Math.min(cameraWidth, (dx - offsetX) / scale)),
        ),
        y: Math.round(
          Math.max(0, Math.min(cameraHeight, (dy - offsetY) / scale)),
        ),
      }),
    });
  }, [containerRef, cameraWidth, cameraHeight]);

  useEffect(() => {
    calculate();

    const container = containerRef.current;
    if (!container) return () => {};

    const observer = new ResizeObserver(() => {
      calculate();
    });
    observer.observe(container);

    return () => {
      observer.disconnect();
    };
  }, [calculate, containerRef]);

  return transform;
}
