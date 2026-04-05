import { useCallback, useEffect, useRef, useState } from "react";

import {
  drawPolygons,
  findNearEdgeMidpoint,
  findNearVertex,
  findPolygonAtPoint,
} from "./canvasRenderer";
import { CoordinateTransform, Point, Polygon } from "./types";
import { usePolygonEditorStore } from "./usePolygonEditorStore";

const EDGE_SNAP_THRESHOLD = 15; // pixels in camera coords to snap to edge

interface PolygonCanvasProps {
  containerRef: React.RefObject<HTMLElement | null>;
  transform: CoordinateTransform;
  polygons: Polygon[];
  isEditing: boolean;
  cameraWidth: number;
  cameraHeight: number;
}

/**
 * Clamp to image bounds and snap to edges when close.
 */
function clampAndSnap(
  point: Point,
  cameraWidth: number,
  cameraHeight: number,
): Point {
  let { x, y } = point;

  // Clamp
  x = Math.max(0, Math.min(cameraWidth, x));
  y = Math.max(0, Math.min(cameraHeight, y));

  // Snap to edges
  if (x < EDGE_SNAP_THRESHOLD) x = 0;
  if (x > cameraWidth - EDGE_SNAP_THRESHOLD) x = cameraWidth;
  if (y < EDGE_SNAP_THRESHOLD) y = 0;
  if (y > cameraHeight - EDGE_SNAP_THRESHOLD) y = cameraHeight;

  return { x: Math.round(x), y: Math.round(y) };
}

export function PolygonCanvas({
  containerRef,
  transform,
  polygons,
  isEditing,
  cameraWidth,
  cameraHeight,
}: PolygonCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [dragging, setDragging] = useState<{
    polygonId: string;
    vertexIndex: number;
  } | null>(null);
  const draggingRef = useRef(dragging);
  draggingRef.current = dragging;

  const {
    selectedPolygonId,
    hoveredVertexInfo,
    selectPolygon,
    moveVertex,
    addVertex,
    deleteVertex,
  } = usePolygonEditorStore();

  // Resize canvas to match container
  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return () => {};

    const observer = new ResizeObserver(() => {
      const rect = container.getBoundingClientRect();
      canvas.width = rect.width;
      canvas.height = rect.height;
    });

    observer.observe(container);
    const rect = container.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    return () => observer.disconnect();
  }, [containerRef]);

  // Redraw on any change
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    drawPolygons(ctx, polygons, transform, selectedPolygonId, hoveredVertexInfo);
  }, [polygons, transform, selectedPolygonId, hoveredVertexInfo]);

  const getCanvasPos = useCallback(
    (e: React.PointerEvent | React.MouseEvent) => {
      const canvas = canvasRef.current;
      if (!canvas) return { x: 0, y: 0 };
      const rect = canvas.getBoundingClientRect();
      return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    },
    [],
  );

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (!isEditing || e.button !== 0) return;
      const pos = getCanvasPos(e);

      // If a polygon is selected, check for vertex drag
      if (selectedPolygonId) {
        const polygon = polygons.find((p) => p.id === selectedPolygonId);
        if (polygon) {
          const vertexIdx = findNearVertex(pos.x, pos.y, polygon, transform);
          if (vertexIdx >= 0) {
            setDragging({ polygonId: polygon.id, vertexIndex: vertexIdx });
            // Capture pointer for tracking outside canvas/window
            (e.target as HTMLElement).setPointerCapture(e.pointerId);
            e.preventDefault();
            return;
          }

          // Check edge midpoints for adding a vertex
          const edgeIdx = findNearEdgeMidpoint(
            pos.x,
            pos.y,
            polygon,
            transform,
          );
          if (edgeIdx >= 0) {
            const cameraPoint = clampAndSnap(
              transform.toCamera(pos.x, pos.y),
              cameraWidth,
              cameraHeight,
            );
            addVertex(polygon.id, edgeIdx, cameraPoint);
            e.preventDefault();
            return;
          }
        }
      }

      // Click on a polygon to select it
      const clickedId = findPolygonAtPoint(pos.x, pos.y, polygons, transform);
      selectPolygon(clickedId);
    },
    [
      isEditing,
      selectedPolygonId,
      polygons,
      transform,
      cameraWidth,
      cameraHeight,
      getCanvasPos,
      selectPolygon,
      addVertex,
    ],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!isEditing) return;
      const pos = getCanvasPos(e);

      if (draggingRef.current) {
        const raw = transform.toCamera(pos.x, pos.y);
        const cameraPoint = clampAndSnap(raw, cameraWidth, cameraHeight);
        moveVertex(
          draggingRef.current.polygonId,
          draggingRef.current.vertexIndex,
          cameraPoint,
        );
        return;
      }

      // Update hover state for vertex highlighting
      if (selectedPolygonId) {
        const polygon = polygons.find((p) => p.id === selectedPolygonId);
        if (polygon) {
          const vertexIdx = findNearVertex(pos.x, pos.y, polygon, transform);
          if (vertexIdx >= 0) {
            usePolygonEditorStore.setState({
              hoveredVertexInfo: {
                polygonId: polygon.id,
                vertexIndex: vertexIdx,
              },
            });
            return;
          }
        }
      }
      usePolygonEditorStore.setState({ hoveredVertexInfo: null });
    },
    [
      isEditing,
      selectedPolygonId,
      polygons,
      transform,
      cameraWidth,
      cameraHeight,
      getCanvasPos,
      moveVertex,
    ],
  );

  const handlePointerUp = useCallback(
    (e: React.PointerEvent) => {
      if (draggingRef.current) {
        (e.target as HTMLElement).releasePointerCapture(e.pointerId);
      }
      setDragging(null);
    },
    [],
  );

  const handleContextMenu = useCallback(
    (e: React.MouseEvent) => {
      if (!isEditing || !selectedPolygonId) return;
      e.preventDefault();

      const pos = getCanvasPos(e);
      const polygon = polygons.find((p) => p.id === selectedPolygonId);
      if (!polygon) return;

      const vertexIdx = findNearVertex(pos.x, pos.y, polygon, transform);
      if (vertexIdx >= 0 && polygon.points.length > 3) {
        deleteVertex(polygon.id, vertexIdx);
      }
    },
    [
      isEditing,
      selectedPolygonId,
      polygons,
      transform,
      getCanvasPos,
      deleteVertex,
    ],
  );

  return (
    <canvas
      ref={canvasRef}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onContextMenu={handleContextMenu}
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        zIndex: isEditing ? 4 : 2,
        pointerEvents: isEditing ? "auto" : "none",
        touchAction: "none",
        cursor: dragging
          ? "grabbing"
          : hoveredVertexInfo
            ? "grab"
            : isEditing
              ? "crosshair"
              : "default",
      }}
    />
  );
}
