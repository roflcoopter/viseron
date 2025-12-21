import { Coordinate } from "./types";

interface DrawingOverlayProps {
  drawingType: "zone" | "mask" | null;
  drawingPoints: Coordinate[];
}

export function DrawingOverlay({
  drawingType,
  drawingPoints,
}: DrawingOverlayProps) {
  if (drawingPoints.length === 0) return null;

  const color = drawingType === "zone" ? "#00ff00" : "#ff0000";
  const fillColor =
    drawingType === "zone" ? "rgba(0, 255, 0, 0.15)" : "rgba(255, 0, 0, 0.15)";

  return (
    <>
      {/* Draw filled polygon if 3 or more points */}
      {drawingPoints.length >= 3 && (
        <polygon
          points={drawingPoints
            .map((point) => `${point.x},${point.y}`)
            .join(" ")}
          fill={fillColor}
          stroke="none"
        />
      )}
      {/* Draw lines between points */}
      {drawingPoints.map((point, index) => {
        if (index === 0) return null;
        const prevPoint = drawingPoints[index - 1];
        return (
          <line
            key={`line-${prevPoint.x}-${prevPoint.y}-${point.x}-${point.y}`}
            x1={prevPoint.x}
            y1={prevPoint.y}
            x2={point.x}
            y2={point.y}
            stroke={color}
            strokeWidth="2"
          />
        );
      })}
      {/* Draw closing line (dashed) */}
      {drawingPoints.length >= 2 && (
        <line
          x1={drawingPoints[drawingPoints.length - 1].x}
          y1={drawingPoints[drawingPoints.length - 1].y}
          x2={drawingPoints[0].x}
          y2={drawingPoints[0].y}
          stroke={color}
          strokeWidth="2"
          strokeDasharray="5,5"
        />
      )}
      {/* Draw points */}
      {drawingPoints.map((point) => (
        <circle
          key={`point-${point.x}-${point.y}`}
          cx={point.x}
          cy={point.y}
          r="15"
          fill={color}
          stroke="white"
          strokeWidth="3"
        />
      ))}
    </>
  );
}
