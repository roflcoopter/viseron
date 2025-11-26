/**
 * Miscellaneous field configuration for motion_detector domain
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
 * Configuration for motion_detector domain
 * Use "*" as key to apply to all component types, or specify exact component name
 */
export const MOTION_DETECTOR_MISCELLANEOUS_CONFIG: {
  [componentType: string]: MiscellaneousFieldConfig[];
} = {
  mog2: [
    {
      key: "history",
      label: "History",
      description:
        "The number of last frames that affect the background model.",
      type: "integer",
      default: 500,
    },
    {
      key: "detect_shadows",
      label: "Detect Shadows",
      description:
        "Enable/disable shadow detection. If enabled, shadows will be considered as motion at the expense of some extra resources.",
      type: "boolean",
      default: false,
    },
    {
      key: "learning_rate",
      label: "Learning Rate",
      description:
        "How fast the background model learns. 0 means that the background model is not updated at all, 1 means that the background model is completely reinitialized from the last frame. Negative values gives an automatically chosen learning rate.",
      type: "float",
      default: 0.01,
      lowest: -1,
      highest: 1,
    },
  ],
  background_subtractor: [
    {
      key: "alpha",
      label: "Alpha",
      description:
        "How much the current image impacts the moving average. Higher values impacts the average frame a lot and very small changes may trigger motion. Lower value impacts the average less, and fast objects may not trigger motion.",
      type: "float",
      default: 0.01,
      lowest: 0,
      highest: 1,
    },
  ],
  "*": [
    // Applies to all motion detector types
    {
      key: "trigger_event_recording",
      label: "Trigger Event Recording",
      description: "If true, detected motion will trigger an event recording.",
      type: "boolean",
      default: false,
    },
    {
      key: "recorder_keepalive",
      label: "Recorder Keepalive",
      description:
        "If true, recording will continue until no motion is detected.",
      type: "boolean",
      default: true,
    },
    {
      key: "fps",
      label: "FPS",
      description:
        "The FPS at which the motion detector runs. Higher values will result in more scanning, which uses more resources.",
      type: "integer",
      default: 1,
      lowest: 1,
    },
    {
      key: "area",
      label: "Area",
      description:
        "How big the detected area must be in order to trigger motion.",
      type: "float",
      default: 0.08,
      lowest: 0,
      highest: 1,
    },
    {
      key: "threshold",
      label: "Threshold",
      description:
        "The minimum allowed difference between our current frame and averaged frame for a given pixel to be considered motion. A smaller value leads to higher sensitivity and a larger value leads to lower sensitivity.",
      type: "integer",
      default: 15,
      lowest: 0,
      highest: 255,
    },
  ],
};
