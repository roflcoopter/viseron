export interface Point {
  x: number;
  y: number;
}

export type PolygonCategory = "motion_mask" | "object_mask" | "zone";

export interface Polygon {
  id: string;
  category: PolygonCategory;
  name?: string;
  points: Point[];
  // Preserve zone labels config for round-tripping
  labels?: Array<Record<string, unknown>>;
  // Track which component this came from
  componentKey: string;
}

export interface CoordinateTransform {
  toDisplay: (p: Point) => { x: number; y: number };
  toCamera: (dx: number, dy: number) => Point;
  scale: number;
  offsetX: number;
  offsetY: number;
}

export const CATEGORY_COLORS: Record<PolygonCategory, string> = {
  motion_mask: "rgba(255, 60, 60, 0.35)",
  object_mask: "rgba(60, 120, 255, 0.35)",
  zone: "rgba(60, 200, 60, 0.35)",
};

export const CATEGORY_STROKE_COLORS: Record<PolygonCategory, string> = {
  motion_mask: "rgba(255, 60, 60, 0.9)",
  object_mask: "rgba(60, 120, 255, 0.9)",
  zone: "rgba(60, 200, 60, 0.9)",
};

export const CATEGORY_LABELS: Record<PolygonCategory, string> = {
  motion_mask: "Motion Mask",
  object_mask: "Object Mask",
  zone: "Zone",
};
