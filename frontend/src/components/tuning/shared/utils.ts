import { Camera, Coordinate } from "./types";

/**
 * Calculate image coordinates from a click event
 * Converts screen coordinates to image coordinates accounting for aspect ratio and padding
 */
export function calculateImageCoordinates(
  event: React.MouseEvent<HTMLDivElement>,
  camera: Camera,
): Coordinate | null {
  const target = event.currentTarget;
  const rect = target.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;

  // Calculate image dimensions within container
  const containerWidth = rect.width;
  const containerHeight = rect.height;
  const imageAspectRatio = camera.still_image.width / camera.still_image.height;
  const containerAspectRatio = containerWidth / containerHeight;

  let imageWidth;
  let imageHeight;
  let offsetX;
  let offsetY;

  if (containerAspectRatio > imageAspectRatio) {
    // Container is wider than image
    imageHeight = containerHeight;
    imageWidth = imageHeight * imageAspectRatio;
    offsetX = (containerWidth - imageWidth) / 2;
    offsetY = 0;
  } else {
    // Container is taller than image
    imageWidth = containerWidth;
    imageHeight = imageWidth / imageAspectRatio;
    offsetX = 0;
    offsetY = (containerHeight - imageHeight) / 2;
  }

  // Convert to image coordinates
  const imageX = ((x - offsetX) / imageWidth) * camera.still_image.width;
  const imageY = ((y - offsetY) / imageHeight) * camera.still_image.height;

  // Check if click is within image bounds
  if (
    imageX >= 0 &&
    imageX <= camera.still_image.width &&
    imageY >= 0 &&
    imageY <= camera.still_image.height
  ) {
    return { x: Math.round(imageX), y: Math.round(imageY) };
  }

  return null;
}

/**
 * Calculate the centroid (center point) of a polygon
 */
export function calculatePolygonCentroid(
  coordinates: Coordinate[],
): Coordinate {
  const centroidX =
    coordinates.reduce((sum, coord) => sum + coord.x, 0) / coordinates.length;
  const centroidY =
    coordinates.reduce((sum, coord) => sum + coord.y, 0) / coordinates.length;
  return { x: centroidX, y: centroidY };
}

/**
 * Convert polygon coordinates array to SVG points string
 */
export function coordinatesToSVGPoints(coordinates: Coordinate[]): string {
  return coordinates.map((coord) => `${coord.x},${coord.y}`).join(" ");
}

/**
 * Update a single point in a polygon's coordinates
 * Generic helper to avoid duplication between zone and mask handlers
 */
export function updatePolygonPoint<T extends { coordinates: Coordinate[] }>(
  items: T[],
  itemIndex: number,
  pointIndex: number,
  newX: number,
  newY: number,
): T[] {
  const updatedItems = [...items];
  const updatedCoordinates = [...updatedItems[itemIndex].coordinates];
  updatedCoordinates[pointIndex] = { x: Math.round(newX), y: Math.round(newY) };
  updatedItems[itemIndex] = {
    ...updatedItems[itemIndex],
    coordinates: updatedCoordinates,
  };
  return updatedItems;
}

/**
 * Drag entire polygon by delta offset, with boundary constraints
 * Generic helper to avoid duplication between zone and mask handlers
 */
export function dragPolygon<T extends { coordinates: Coordinate[] }>(
  items: T[],
  itemIndex: number,
  deltaX: number,
  deltaY: number,
  imageWidth: number,
  imageHeight: number,
): T[] {
  const updatedItems = [...items];
  const updatedCoordinates = updatedItems[itemIndex].coordinates.map(
    (coord: Coordinate) => {
      const newX = Math.max(0, Math.min(imageWidth, coord.x + deltaX));
      const newY = Math.max(0, Math.min(imageHeight, coord.y + deltaY));
      return { x: Math.round(newX), y: Math.round(newY) };
    },
  );

  updatedItems[itemIndex] = {
    ...updatedItems[itemIndex],
    coordinates: updatedCoordinates,
  };

  return updatedItems;
}
