/**
 * Miscellaneous field configuration for camera domain
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
 * Configuration for camera domain
 * Use "*" as key to apply to all component types, or specify exact component name
 */
export const CAMERA_MISCELLANEOUS_CONFIG: {
  [componentType: string]: MiscellaneousFieldConfig[];
} = {
  ffmpeg: [
    {
      key: "record_only",
      label: "Record Only",
      description:
        "Only record the camera stream, do not process it. This is useful if you only want to record the stream and not do any processing like object detection. Be aware that this will record the main stream, making substream redundant. Still images will not work either unless you have setup 'still_image'.",
      type: "boolean",
      default: false,
    },
  ],
  "*": [
    // Applies to all camera types
    {
      key: "stream_format",
      label: "Stream Format",
      description: "Stream format",
      type: "enum",
      default: "rtsp",
      options: ["rtsp", "rtmp", "mjpeg"],
    },
    {
      key: "rtsp_transport",
      label: "RTSP transport",
      description:
        "Sets RTSP transport protocol. Change this if your camera doesn't support TCP.",
      type: "enum",
      default: "tcp",
      options: ["tcp", "udp", "udp_multicast", "http"],
    },
    {
      key: "fps",
      label: "FPS",
      description:
        "FPS of the stream. Will use FFprobe to get this information if not given, see FFprobe stream information.",
      type: "integer",
      default: null,
      lowest: 1,
      highest: 100,
    },
    {
      key: "width",
      label: "Width",
      description:
        "Width of the stream. Will use FFprobe to get this information if not given, see FFprobe stream information.",
      type: "integer",
      default: null,
      lowest: 320,
      highest: 7680,
    },
    {
      key: "height",
      label: "Height",
      description:
        "Height of the stream. Will use FFprobe to get this information if not given, see FFprobe stream information.",
      type: "integer",
      default: null,
      lowest: 240,
      highest: 4320,
    },
  ],
};
