/**
 * Miscellaneous field configuration for object_detector domain
 *
 * Define editable fields that will appear in the Miscellaneous section.
 * These fields are domain-specific and can be customized per component type.
 */

export interface MiscellaneousFieldConfig {
  key: string;
  label: string;
  description?: string;
  type: "string" | "integer" | "float" | "boolean" | "enum";
  default?: any;
  lowest?: number;
  highest?: number;
  options?: string[];
}

/**
 * Configuration for object_detector domain
 * Use "*" as key to apply to all component types, or specify exact component name
 */
export const OBJECT_DETECTOR_MISCELLANEOUS_CONFIG: {
  [componentType: string]: MiscellaneousFieldConfig[];
} = {
  "*": [
    // Applies to all object detector types
    {
      key: "fps",
      label: "FPS",
      description:
        "Frames per second for object detection. Lower values reduce CPU/GPU usage but may miss fast-moving objects.",
      type: "integer",
      default: 1,
      lowest: 1,
    },
    {
      key: "scan_on_motion_only",
      label: "Scan on Motion Only",
      description:
        "Only run object detection when motion is detected. Saves resources but requires motion detector to be configured.",
      type: "boolean",
      default: false,
    },
    {
      key: "max_frame_age",
      label: "Max Frame Age",
      description:
        "Drop frames that are older than the given number. Specified in seconds.",
      type: "float",
      default: 2,
      lowest: 1,
    },
    {
      key: "log_all_objects",
      label: "Log All Objects",
      description:
        "When set to true and loglevel is DEBUG, all found objects will be logged, including the ones not tracked by labels.",
      type: "boolean",
      default: false,
    },
  ],
  // Example for specific component type:
  // "darknet": [
  //   {
  //     key: "custom_field",
  //     label: "Custom Field",
  //     type: "string",
  //   },
  // ],
};
