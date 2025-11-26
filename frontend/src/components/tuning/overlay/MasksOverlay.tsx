import { DragHandlers, MaskData } from "./types";
import {
  calculateCentroid,
  clampCoordinate,
  coordinatesToPoints,
} from "./utils";

interface MasksOverlayProps {
  masks: MaskData[];
  selectedMaskIndex: number | null;
  imageWidth: number;
  imageHeight: number;
  dragHandlers: DragHandlers;
}

export function MasksOverlay({
  masks,
  selectedMaskIndex,
  imageWidth,
  imageHeight,
  dragHandlers,
}: MasksOverlayProps) {
  const { onPointDrag, onPolygonDrag } = dragHandlers;

  return (
    <>
      {masks.map((mask, index) => {
        if (!mask.coordinates || mask.coordinates.length === 0) return null;
        const points = coordinatesToPoints(mask.coordinates);
        const isSelected = selectedMaskIndex === index;
        const maskKey = mask.name || `mask-${points.substring(0, 20)}`;
        const centroid = calculateCentroid(mask.coordinates);

        return (
          <g key={maskKey}>
            <polygon
              points={points}
              fill={
                isSelected ? "rgba(255, 0, 0, 0.4)" : "rgba(255, 0, 0, 0.15)"
              }
              stroke={isSelected ? "#ff0000" : "#ff0000"}
              strokeWidth={isSelected ? "3" : "2"}
              style={{
                cursor: isSelected && onPolygonDrag ? "grab" : "default",
                pointerEvents: isSelected && onPolygonDrag ? "auto" : "none",
              }}
              onMouseDown={(e) => {
                if (!isSelected || !onPolygonDrag) return;
                e.preventDefault();
                e.stopPropagation();
                const svg = e.currentTarget.ownerSVGElement;
                if (!svg) return;

                const polygon = e.currentTarget as SVGPolygonElement;
                polygon.style.cursor = "grabbing";

                const rect = svg.getBoundingClientRect();
                const scaleX = imageWidth / rect.width;
                const scaleY = imageHeight / rect.height;
                const startX = e.clientX;
                const startY = e.clientY;

                const handleMouseMove = (moveEvent: globalThis.MouseEvent) => {
                  moveEvent.preventDefault();
                  const deltaX = (moveEvent.clientX - startX) * scaleX;
                  const deltaY = (moveEvent.clientY - startY) * scaleY;
                  onPolygonDrag(
                    "mask",
                    index,
                    deltaX,
                    deltaY,
                    imageWidth,
                    imageHeight,
                  );
                };

                const handleMouseUp = (upEvent: globalThis.MouseEvent) => {
                  upEvent.preventDefault();
                  polygon.style.cursor = "grab";
                  document.removeEventListener("mousemove", handleMouseMove);
                  document.removeEventListener("mouseup", handleMouseUp);
                };

                document.addEventListener("mousemove", handleMouseMove);
                document.addEventListener("mouseup", handleMouseUp);
              }}
            />
            {/* Draw points if mask is selected */}
            {isSelected &&
              mask.coordinates.map((coord, pointIdx) => (
                <circle
                  key={`mask-point-${maskKey}-${coord.x}-${coord.y}`}
                  cx={coord.x}
                  cy={coord.y}
                  r="15"
                  fill="#ff0000"
                  stroke="white"
                  strokeWidth="2"
                  style={{
                    cursor: onPointDrag ? "move" : "default",
                    pointerEvents: onPointDrag ? "auto" : "none",
                  }}
                  onMouseDown={(e) => {
                    if (!onPointDrag) return;
                    e.preventDefault();
                    e.stopPropagation();
                    const svg = e.currentTarget.ownerSVGElement;
                    if (!svg) return;

                    const handleMouseMove = (
                      moveEvent: globalThis.MouseEvent,
                    ) => {
                      moveEvent.preventDefault();
                      const rect = svg.getBoundingClientRect();
                      const scaleX = imageWidth / rect.width;
                      const scaleY = imageHeight / rect.height;
                      let newX = (moveEvent.clientX - rect.left) * scaleX;
                      let newY = (moveEvent.clientY - rect.top) * scaleY;

                      // Clamp coordinates to stay within image bounds
                      newX = clampCoordinate(newX, 0, imageWidth);
                      newY = clampCoordinate(newY, 0, imageHeight);

                      onPointDrag("mask", index, pointIdx, newX, newY);
                    };

                    const handleMouseUp = (upEvent: globalThis.MouseEvent) => {
                      upEvent.preventDefault();
                      document.removeEventListener(
                        "mousemove",
                        handleMouseMove,
                      );
                      document.removeEventListener("mouseup", handleMouseUp);
                    };

                    document.addEventListener("mousemove", handleMouseMove);
                    document.addEventListener("mouseup", handleMouseUp);
                  }}
                />
              ))}
            <text
              x={centroid.x}
              y={centroid.y}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="#ff0000"
              stroke="black"
              strokeWidth="1"
              fontSize="30"
              fontWeight="bold"
            >
              {mask.name || `Mask ${index + 1}`}
            </text>
          </g>
        );
      })}
    </>
  );
}
