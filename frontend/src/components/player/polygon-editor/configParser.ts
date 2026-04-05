import yaml from "js-yaml";
import { v4 as uuidv4 } from "uuid";

import { Point, Polygon, PolygonCategory } from "./types";

interface YamlCoordinate {
  x: number;
  y: number;
}

interface YamlMaskEntry {
  coordinates: YamlCoordinate[];
}

interface YamlZoneEntry {
  name: string;
  coordinates: YamlCoordinate[];
  labels?: Array<Record<string, unknown>>;
}

function extractPolygonsFromComponent(
  componentKey: string,
  component: Record<string, unknown>,
  cameraIdentifier: string,
  polygons: Polygon[],
): void {
  // Check for motion_detector
  if (component.motion_detector) {
    const md = component.motion_detector as Record<string, unknown>;
    const cameras = md.cameras as Record<string, unknown> | undefined;
    if (cameras && cameras[cameraIdentifier]) {
      const camConfig = cameras[cameraIdentifier] as Record<string, unknown>;
      if (Array.isArray(camConfig.mask)) {
        for (const maskEntry of camConfig.mask as YamlMaskEntry[]) {
          if (Array.isArray(maskEntry.coordinates)) {
            polygons.push({
              id: uuidv4(),
              category: "motion_mask",
              componentKey,
              points: maskEntry.coordinates.map((c) => ({ x: c.x, y: c.y })),
            });
          }
        }
      }
    }
  }

  // Check for object_detector
  if (component.object_detector) {
    const od = component.object_detector as Record<string, unknown>;
    const cameras = od.cameras as Record<string, unknown> | undefined;
    if (cameras && cameras[cameraIdentifier]) {
      const camConfig = cameras[cameraIdentifier] as Record<string, unknown>;

      if (Array.isArray(camConfig.mask)) {
        for (const maskEntry of camConfig.mask as YamlMaskEntry[]) {
          if (Array.isArray(maskEntry.coordinates)) {
            polygons.push({
              id: uuidv4(),
              category: "object_mask",
              componentKey,
              points: maskEntry.coordinates.map((c) => ({ x: c.x, y: c.y })),
            });
          }
        }
      }

      if (Array.isArray(camConfig.zones)) {
        for (const zoneEntry of camConfig.zones as YamlZoneEntry[]) {
          if (Array.isArray(zoneEntry.coordinates)) {
            polygons.push({
              id: uuidv4(),
              category: "zone",
              componentKey,
              name: zoneEntry.name,
              labels: zoneEntry.labels,
              points: zoneEntry.coordinates.map((c) => ({ x: c.x, y: c.y })),
            });
          }
        }
      }
    }
  }
}

/**
 * Parse all polygons (masks and zones) for a given camera from YAML config.
 * Scans all top-level components for motion_detector and object_detector domains.
 */
export function parsePolygonsFromConfig(
  yamlString: string,
  cameraIdentifier: string,
): Polygon[] {
  const config = yaml.load(yamlString) as Record<string, unknown>;
  if (!config || typeof config !== "object") return [];

  const polygons: Polygon[] = [];

  Object.entries(config).forEach(([componentKey, componentValue]) => {
    if (componentValue && typeof componentValue === "object") {
      extractPolygonsFromComponent(
        componentKey,
        componentValue as Record<string, unknown>,
        cameraIdentifier,
        polygons,
      );
    }
  });

  return polygons;
}

function buildMaskArray(polygons: Polygon[]): YamlMaskEntry[] {
  return polygons.map((p) => ({
    coordinates: p.points.map((pt) => ({ x: pt.x, y: pt.y })),
  }));
}

function buildZonesArray(polygons: Polygon[]): YamlZoneEntry[] {
  return polygons.map((p) => ({
    name: p.name || `zone_${p.id.slice(0, 6)}`,
    coordinates: p.points.map((pt) => ({ x: pt.x, y: pt.y })),
    ...(p.labels ? { labels: p.labels } : {}),
  }));
}

function updateComponentMasks(
  component: Record<string, unknown>,
  componentKey: string,
  cameraIdentifier: string,
  grouped: Map<
    string,
    { motion_mask: Polygon[]; object_mask: Polygon[]; zone: Polygon[] }
  >,
): void {
  if (component.motion_detector) {
    const md = component.motion_detector as Record<string, unknown>;
    const cameras = md.cameras as Record<string, unknown> | undefined;
    if (cameras && cameras[cameraIdentifier]) {
      const camConfig = cameras[cameraIdentifier] as Record<string, unknown>;
      const group = grouped.get(componentKey);
      const motionMasks = group?.motion_mask || [];

      if (motionMasks.length > 0) {
        camConfig.mask = buildMaskArray(motionMasks);
      } else {
        delete camConfig.mask;
      }
    }
  }

  if (component.object_detector) {
    const od = component.object_detector as Record<string, unknown>;
    const cameras = od.cameras as Record<string, unknown> | undefined;
    if (cameras && cameras[cameraIdentifier]) {
      const camConfig = cameras[cameraIdentifier] as Record<string, unknown>;
      const group = grouped.get(componentKey);

      const objectMasks = group?.object_mask || [];
      if (objectMasks.length > 0) {
        camConfig.mask = buildMaskArray(objectMasks);
      } else {
        delete camConfig.mask;
      }

      const zones = group?.zone || [];
      if (zones.length > 0) {
        camConfig.zones = buildZonesArray(zones);
      } else {
        delete camConfig.zones;
      }
    }
  }
}

/**
 * Update the YAML config string with modified polygons for a camera.
 */
export function updateConfigWithPolygons(
  yamlString: string,
  cameraIdentifier: string,
  polygons: Polygon[],
): string {
  const config = yaml.load(yamlString) as Record<string, unknown>;
  if (!config || typeof config !== "object") return yamlString;

  const grouped = new Map<
    string,
    { motion_mask: Polygon[]; object_mask: Polygon[]; zone: Polygon[] }
  >();

  for (const poly of polygons) {
    if (!grouped.has(poly.componentKey)) {
      grouped.set(poly.componentKey, {
        motion_mask: [],
        object_mask: [],
        zone: [],
      });
    }
    grouped.get(poly.componentKey)![poly.category].push(poly);
  }

  Object.entries(config).forEach(([componentKey, componentValue]) => {
    if (componentValue && typeof componentValue === "object") {
      updateComponentMasks(
        componentValue as Record<string, unknown>,
        componentKey,
        cameraIdentifier,
        grouped,
      );
    }
  });

  return yaml.dump(config, {
    indent: 2,
    lineWidth: -1,
    noRefs: true,
    sortKeys: false,
  });
}

/**
 * Detect which components are available for each category.
 */
export function detectComponents(
  yamlString: string,
  cameraIdentifier: string,
): {
  motionComponent: string | null;
  objectComponent: string | null;
} {
  const config = yaml.load(yamlString) as Record<string, unknown>;
  if (!config || typeof config !== "object")
    return { motionComponent: null, objectComponent: null };

  let motionComponent: string | null = null;
  let objectComponent: string | null = null;

  Object.entries(config).forEach(([componentKey, componentValue]) => {
    if (!componentValue || typeof componentValue !== "object") return;
    const component = componentValue as Record<string, unknown>;

    if (component.motion_detector && !motionComponent) {
      const md = component.motion_detector as Record<string, unknown>;
      const cameras = md.cameras as Record<string, unknown> | undefined;
      if (cameras && cameras[cameraIdentifier]) {
        motionComponent = componentKey;
      }
    }

    if (component.object_detector && !objectComponent) {
      const od = component.object_detector as Record<string, unknown>;
      const cameras = od.cameras as Record<string, unknown> | undefined;
      if (cameras && cameras[cameraIdentifier]) {
        objectComponent = componentKey;
      }
    }
  });

  return { motionComponent, objectComponent };
}

/**
 * Create a default polygon centered in the camera frame.
 */
export function createDefaultPolygon(
  category: PolygonCategory,
  componentKey: string,
  cameraWidth: number,
  cameraHeight: number,
): Polygon {
  const cx = Math.round(cameraWidth / 2);
  const cy = Math.round(cameraHeight / 2);
  const size = Math.round(Math.min(cameraWidth, cameraHeight) / 6);

  const points: Point[] = [
    { x: cx - size, y: cy - size },
    { x: cx + size, y: cy - size },
    { x: cx + size, y: cy + size },
    { x: cx - size, y: cy + size },
  ];

  return {
    id: uuidv4(),
    category,
    componentKey,
    points,
    ...(category === "zone" ? { name: `zone_${Date.now().toString(36)}` } : {}),
  };
}
