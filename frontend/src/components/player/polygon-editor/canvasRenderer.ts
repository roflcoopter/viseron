import {
  CATEGORY_COLORS,
  CATEGORY_LABELS,
  CATEGORY_STROKE_COLORS,
  CoordinateTransform,
  Polygon,
} from "./types";

const VERTEX_RADIUS = 6;
const SELECTED_VERTEX_RADIUS = 8;
const EDGE_HIT_DISTANCE = 8;

function isPointInPolygon(
  x: number,
  y: number,
  points: { x: number; y: number }[],
): boolean {
  let inside = false;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const xi = points[i].x;
    const yi = points[i].y;
    const xj = points[j].x;
    const yj = points[j].y;

    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

function drawSinglePolygon(
  ctx: CanvasRenderingContext2D,
  polygon: Polygon,
  transform: CoordinateTransform,
  isSelected: boolean,
  hoveredVertexInfo: { polygonId: string; vertexIndex: number } | null,
): void {
  const displayPoints = polygon.points.map((p) => transform.toDisplay(p));

  if (displayPoints.length < 2) return;

  // Fill
  ctx.beginPath();
  ctx.moveTo(displayPoints[0].x, displayPoints[0].y);
  for (let i = 1; i < displayPoints.length; i++) {
    ctx.lineTo(displayPoints[i].x, displayPoints[i].y);
  }
  ctx.closePath();

  const fillColor = isSelected
    ? CATEGORY_COLORS[polygon.category].replace("0.35", "0.45")
    : CATEGORY_COLORS[polygon.category];
  ctx.fillStyle = fillColor;
  ctx.fill();

  // Stroke
  ctx.strokeStyle = CATEGORY_STROKE_COLORS[polygon.category];
  ctx.lineWidth = isSelected ? 3 : 2;
  if (!isSelected) {
    ctx.setLineDash([6, 4]);
  } else {
    ctx.setLineDash([]);
  }
  ctx.stroke();
  ctx.setLineDash([]);

  // Label
  if (displayPoints.length >= 3) {
    const centerX =
      displayPoints.reduce((s, p) => s + p.x, 0) / displayPoints.length;
    const centerY =
      displayPoints.reduce((s, p) => s + p.y, 0) / displayPoints.length;

    const label =
      polygon.category === "zone" && polygon.name
        ? polygon.name
        : CATEGORY_LABELS[polygon.category];

    ctx.font = "bold 12px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    const metrics = ctx.measureText(label);
    const textHeight = 16;
    ctx.fillStyle = "rgba(0, 0, 0, 0.6)";
    ctx.fillRect(
      centerX - metrics.width / 2 - 4,
      centerY - textHeight / 2 - 2,
      metrics.width + 8,
      textHeight + 4,
    );

    ctx.fillStyle = "#ffffff";
    ctx.fillText(label, centerX, centerY);
  }

  // Vertices (only for selected polygon)
  if (isSelected) {
    for (let i = 0; i < displayPoints.length; i++) {
      const isHovered =
        hoveredVertexInfo?.polygonId === polygon.id &&
        hoveredVertexInfo?.vertexIndex === i;
      const radius = isHovered ? SELECTED_VERTEX_RADIUS : VERTEX_RADIUS;

      ctx.beginPath();
      ctx.arc(
        displayPoints[i].x,
        displayPoints[i].y,
        radius,
        0,
        Math.PI * 2,
      );
      ctx.fillStyle = isHovered ? "#ffff00" : "#ffffff";
      ctx.fill();
      ctx.strokeStyle = CATEGORY_STROKE_COLORS[polygon.category];
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.font = "bold 10px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillStyle = "#000000";
      ctx.fillText(String(i), displayPoints[i].x, displayPoints[i].y);
    }

    // Edge midpoints (add vertex hint)
    for (let i = 0; i < displayPoints.length; i++) {
      const next = (i + 1) % displayPoints.length;
      const midX = (displayPoints[i].x + displayPoints[next].x) / 2;
      const midY = (displayPoints[i].y + displayPoints[next].y) / 2;

      ctx.beginPath();
      ctx.arc(midX, midY, 4, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(255, 255, 255, 0.5)";
      ctx.fill();
      ctx.strokeStyle = CATEGORY_STROKE_COLORS[polygon.category];
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  }
}

export function drawPolygons(
  ctx: CanvasRenderingContext2D,
  polygons: Polygon[],
  transform: CoordinateTransform,
  selectedPolygonId: string | null,
  hoveredVertexInfo: { polygonId: string; vertexIndex: number } | null,
): void {
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);

  // Draw non-selected polygons first, then selected on top
  const sorted = [...polygons].sort((a, b) => {
    if (a.id === selectedPolygonId) return 1;
    if (b.id === selectedPolygonId) return -1;
    return 0;
  });

  sorted.forEach((polygon) => {
    const isSelected = polygon.id === selectedPolygonId;
    drawSinglePolygon(ctx, polygon, transform, isSelected, hoveredVertexInfo);
  });
}

export function findNearVertex(
  x: number,
  y: number,
  polygon: Polygon,
  transform: CoordinateTransform,
  threshold = SELECTED_VERTEX_RADIUS + 4,
): number {
  const displayPoints = polygon.points.map((p) => transform.toDisplay(p));
  for (let i = 0; i < displayPoints.length; i++) {
    const dx = x - displayPoints[i].x;
    const dy = y - displayPoints[i].y;
    if (Math.sqrt(dx * dx + dy * dy) <= threshold) {
      return i;
    }
  }
  return -1;
}

export function findNearEdgeMidpoint(
  x: number,
  y: number,
  polygon: Polygon,
  transform: CoordinateTransform,
): number {
  const displayPoints = polygon.points.map((p) => transform.toDisplay(p));
  for (let i = 0; i < displayPoints.length; i++) {
    const next = (i + 1) % displayPoints.length;
    const midX = (displayPoints[i].x + displayPoints[next].x) / 2;
    const midY = (displayPoints[i].y + displayPoints[next].y) / 2;
    const dx = x - midX;
    const dy = y - midY;
    if (Math.sqrt(dx * dx + dy * dy) <= EDGE_HIT_DISTANCE) {
      return i;
    }
  }
  return -1;
}

export function findPolygonAtPoint(
  x: number,
  y: number,
  polygons: Polygon[],
  transform: CoordinateTransform,
): string | null {
  for (let pi = polygons.length - 1; pi >= 0; pi--) {
    const polygon = polygons[pi];
    const displayPoints = polygon.points.map((p) => transform.toDisplay(p));
    if (isPointInPolygon(x, y, displayPoints)) {
      return polygon.id;
    }
  }
  return null;
}
