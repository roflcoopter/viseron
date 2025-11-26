import { DragHandlers, ZoneData } from "./types";
import {
  calculateCentroid,
  clampCoordinate,
  coordinatesToPoints,
} from "./utils";

interface ZonesOverlayProps {
  zones: ZoneData[];
  selectedZoneIndex: number | null;
  imageWidth: number;
  imageHeight: number;
  dragHandlers: DragHandlers;
}

export function ZonesOverlay({
  zones,
  selectedZoneIndex,
  imageWidth,
  imageHeight,
  dragHandlers,
}: ZonesOverlayProps) {
  const { onPointDrag, onPolygonDrag } = dragHandlers;

  return (
    <>
      {zones.map((zone, index) => {
        if (!zone.coordinates || zone.coordinates.length === 0) return null;
        const points = coordinatesToPoints(zone.coordinates);
        const isSelected = selectedZoneIndex === index;
        const zoneKey = zone.name || `zone-${points.substring(0, 20)}`;
        const centroid = calculateCentroid(zone.coordinates);

        return (
          <g key={zoneKey}>
            <polygon
              points={points}
              fill={
                isSelected ? "rgba(0, 255, 0, 0.4)" : "rgba(0, 255, 0, 0.15)"
              }
              stroke={isSelected ? "#00ff00" : "#00ff00"}
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
                    "zone",
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
            {/* Draw points if zone is selected */}
            {isSelected &&
              zone.coordinates.map((coord, pointIdx) => (
                <circle
                  key={`zone-point-${zoneKey}-${coord.x}-${coord.y}`}
                  cx={coord.x}
                  cy={coord.y}
                  r="15"
                  fill="#00ff00"
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

                      onPointDrag("zone", index, pointIdx, newX, newY);
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
              fill="#00ff00"
              stroke="black"
              strokeWidth="1"
              fontSize="30"
              fontWeight="bold"
            >
              {zone.name || `Zone ${index + 1}`}
            </text>
          </g>
        );
      })}
    </>
  );
}
