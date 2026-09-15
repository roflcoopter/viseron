import { CAMERA_MISCELLANEOUS_CONFIG } from "../camera/miscellaneousConfig";
import { MOTION_DETECTOR_MISCELLANEOUS_CONFIG } from "../motion_detector/miscellaneousConfig";
import { OBJECT_DETECTOR_MISCELLANEOUS_CONFIG } from "../object_detector/miscellaneousConfig";
import { ONVIF_MISCELLANEOUS_CONFIG } from "../onvif/miscellaneousConfig";
import { MiscellaneousField } from "./MiscellaneousSection";

/**
 * Centralized configuration aggregator for miscellaneous fields.
 *
 * This file imports and aggregates configurations from individual domain folders:
 * - camera/miscellaneousConfig.ts
 * - object_detector/miscellaneousConfig.ts
 * - motion_detector/miscellaneousConfig.ts
 * - face_recognition/miscellaneousConfig.ts
 *
 * TO ADD NEW EDITABLE FIELDS:
 * 1. Go to the appropriate domain folder (e.g., object_detector/)
 * 2. Edit the miscellaneousConfig.ts file in that folder
 * 3. Add your field definition to the config object
 *
 * Example in object_detector/miscellaneousConfig.ts:
 * ```
 * export const OBJECT_DETECTOR_MISCELLANEOUS_CONFIG = {
 *   "*": [  // Applies to all object detector types
 *     {
 *       key: "fps",           // Field name in API
 *       label: "FPS",         // Display label in UI
 *       type: "number",       // Input type: "string" | "number" | "boolean"
 *     },
 *   ],
 * };
 * ```
 */
export const MISCELLANEOUS_CONFIG: {
  [domain: string]: {
    [componentType: string]: {
      key: string;
      label: string;
      description?: string;
      type: "string" | "integer" | "float" | "boolean" | "enum";
      default?: any;
      lowest?: number;
      highest?: number;
      options?: string[];
    }[];
  };
} = {
  camera: CAMERA_MISCELLANEOUS_CONFIG,
  object_detector: OBJECT_DETECTOR_MISCELLANEOUS_CONFIG,
  motion_detector: MOTION_DETECTOR_MISCELLANEOUS_CONFIG,
  onvif: ONVIF_MISCELLANEOUS_CONFIG,
};

/**
 * Get editable miscellaneous fields for a given domain and component type
 */
export function getMiscellaneousFields(
  domain: string,
  componentData: any,
): MiscellaneousField[] {
  const domainConfig = MISCELLANEOUS_CONFIG[domain];
  if (!domainConfig) return [];

  // Get component-specific config if component name is available
  const componentName = componentData?.componentName;
  const componentSpecificConfigs = componentName
    ? domainConfig[componentName] || []
    : [];

  // Get wildcard config (applies to all component types)
  const wildcardConfigs = domainConfig["*"] || [];

  // Merge: component-specific fields come after wildcard fields
  const fieldConfigs = [...wildcardConfigs, ...componentSpecificConfigs];

  return fieldConfigs.map((config) => ({
    key: config.key,
    label: config.label,
    description: config.description,
    type: config.type,
    value:
      componentData[config.key] !== undefined
        ? componentData[config.key]
        : config.default,
    default: config.default,
    lowest: config.lowest,
    highest: config.highest,
    options: config.options,
  }));
}

/**
 * Update a miscellaneous field value in component data
 */
export function updateMiscellaneousField(
  componentData: any,
  key: string,
  value: any,
): any {
  return {
    ...componentData,
    [key]: value,
  };
}
