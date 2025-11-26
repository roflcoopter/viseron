import { Coordinate } from "./types";

export function calculateCentroid(coordinates: Coordinate[]): {
  x: number;
  y: number;
} {
  const x =
    coordinates.reduce((sum, coord) => sum + coord.x, 0) / coordinates.length;
  const y =
    coordinates.reduce((sum, coord) => sum + coord.y, 0) / coordinates.length;
  return { x, y };
}

export function coordinatesToPoints(coordinates: Coordinate[]): string {
  return coordinates.map((coord) => `${coord.x},${coord.y}`).join(" ");
}

export function clampCoordinate(
  value: number,
  min: number,
  max: number,
): number {
  return Math.max(min, Math.min(max, value));
}
