/**
 * Miscellaneous field configuration for onvif component
 *
 * ONVIF is treated as a domain with the following components:
 * - client: Connection settings (port, username, password, etc.)
 * - device: Device service configuration
 * - imaging: Imaging service configuration
 * - media: Media service configuration
 * - ptz: PTZ service configuration
 *
 * Define editable fields that will appear in the Miscellaneous section.
 * These fields are component-specific within the onvif domain.
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
 * Configuration for onvif domain
 * Use component name as key (client, device, imaging, media, ptz)
 */
export const ONVIF_MISCELLANEOUS_CONFIG: {
  [componentType: string]: MiscellaneousFieldConfig[];
} = {
  // Client component - connection/client settings
  client: [
    {
      key: "port",
      label: "Port",
      description: "ONVIF port of the camera.",
      type: "integer",
    },
    {
      key: "username",
      label: "Username",
      description: "ONVIF username for the camera.",
      type: "string",
    },
    {
      key: "password",
      label: "Password",
      description: "ONVIF password for the camera.",
      type: "string",
    },
    {
      key: "timeout",
      label: "Timeout",
      description: "Timeout for ONVIF connections in seconds.",
      type: "integer",
      default: 10,
    },
    {
      key: "use_https",
      label: "Use HTTPS",
      description: "Use HTTPS for ONVIF connections.",
      type: "boolean",
      default: false,
    },
    {
      key: "verify_ssl",
      label: "Verify SSL",
      description: "Verify SSL certificates for ONVIF connections.",
      type: "boolean",
      default: true,
    },
    {
      key: "wsdl_dir",
      label: "WSDL Directory",
      description: "Path to custom WSDL directory for ONVIF client.",
      type: "string",
    },
    {
      key: "auto_config",
      label: "Auto Config",
      description:
        "Set to true then it will ignore all configuration per each service and use the default service that is already on the ONVIF camera. Don't worry! This ONVIF component will automatically detect the existing configuration in the ONVIF camera precisely.",
      type: "boolean",
      default: true,
    },
  ],
  // Device component - only appears if auto_config is false
  device: [
    {
      key: "hostname",
      label: "Hostname",
      description: "The hostname of the device.",
      type: "string",
    },
    {
      key: "discoverable",
      label: "Discoverable",
      description:
        "Whether the device is discoverable on the network via WS-Discovery.",
      type: "boolean",
    },
    {
      key: "datetime_type",
      label: "DateTime Type",
      description: "Defines if the date and time is set via NTP or manually.",
      type: "enum",
      options: ["NTP", "Manual"],
    },
    {
      key: "daylight_savings",
      label: "Daylight Savings",
      description: "Indicates whether Daylight Savings Time is in effect.",
      type: "boolean",
    },
    {
      key: "timezone",
      label: "Timezone",
      description:
        "The time zone in POSIX 1003.1 format. Will be ignored if the datetime_type key is set to NTP.",
      type: "string",
    },
    {
      key: "ntp_from_dhcp",
      label: "NTP from DHCP",
      description:
        "Indicate if NTP address information is to be retrieved using DHCP.",
      type: "boolean",
    },
    {
      key: "ntp_type",
      label: "NTP Type",
      description:
        "Network host type: IPv4, IPv6 or DNS. Will be ignored if the ntp_from_dhcp key is set to true.",
      type: "enum",
      options: ["DNS", "IPv4", "IPv6"],
    },
    {
      key: "ntp_server",
      label: "NTP Server",
      description:
        "The NTP server of the device, for example: pool.ntp.org or time.google.com or 192.168.1.1 (must match with ntp_type). Will be ignored if the ntp_from_dhcp key is set to true.",
      type: "string",
    },
  ],
  // Media component - only appears if auto_config is false
  media: [],
  // Imaging component - only appears if auto_config is false
  imaging: [
    {
      key: "force_persistence",
      label: "Force Persistence",
      description:
        "To determine whether this setting will persist even after a device reboot.",
      default: true,
      type: "boolean",
    },
    {
      key: "brightness",
      label: "Brightness",
      description: "Brightness of the image (unit unspecified).",
      type: "float",
    },
    {
      key: "color_saturation",
      label: "Color Saturation",
      description: "Color saturation of the image (unit unspecified).",
      type: "float",
    },
    {
      key: "contrast",
      label: "Contrast",
      description: "Contrast of the image (unit unspecified).",
      type: "float",
    },
    {
      key: "sharpness",
      label: "Sharpness",
      description: "Sharpness of the image (unit unspecified).",
      type: "float",
    },
    {
      key: "ircut_filter",
      label: "Infrared Cut Filter",
      description: "Infrared Cutoff Filter settings.",
      type: "enum",
      options: ["ON", "OFF", "AUTO"],
    },
    {
      key: "backlight_compensation",
      label: "Backlight Compensation",
      description: "Enabled/disabled Backlight Compensation mode (on/off).",
      type: "enum",
      options: ["ON", "OFF"],
    },
  ],
  // PTZ component - only appears if auto_config is false
  ptz: [
    {
      key: "home_position",
      label: "Home Position",
      description:
        "Move camera to home position on startup (if supported by camera). Will be ignored if any of the PTZ presets have the on_startup set to true.",
      default: false,
      type: "boolean",
    },
    {
      key: "reverse_pan",
      label: "Reverse Pan",
      description:
        "Reverse the pan direction. Will be implemented in backend and frontend, and will not affect the position of user defined PTZ presets.",
      default: false,
      type: "boolean",
    },
    {
      key: "reverse_tilt",
      label: "Reverse Tilt",
      description:
        "Reverse the tilt direction. Will be implemented in backend and frontend, and will not affect the position of user defined PTZ presets.",
      default: false,
      type: "boolean",
    },
    {
      key: "min_pan",
      label: "Minimum Pan",
      description:
        "Minimum pan value of the camera. A value between -1.0 and 1.0 (will be adjusted based on the default ONVIF configuration). Automatically handled by the backend.",
      type: "float",
    },
    {
      key: "max_pan",
      label: "Maximum Pan",
      description:
        "Maximum pan value of the camera. A value between -1.0 and 1.0 (will be adjusted based on the default ONVIF configuration). Automatically handled by the backend.",
      type: "float",
    },
    {
      key: "min_tilt",
      label: "Minimum Tilt",
      description:
        "Minimum tilt value of the camera. A value between -1.0 and 1.0 (will be adjusted based on the default ONVIF configuration). Automatically handled by the backend.",
      type: "float",
    },
    {
      key: "max_tilt",
      label: "Maximum Tilt",
      description:
        "Maximum tilt value of the camera. A value between -1.0 and 1.0 (will be adjusted based on the default ONVIF configuration). Automatically handled by the backend.",
      type: "float",
    },
    {
      key: "min_zoom",
      label: "Minimum Zoom",
      description:
        "Minimum zoom value of the camera. A value between 0.0 and 1.0 (will be adjusted based on the default ONVIF configuration). Automatically handled by the backend.",
      type: "float",
    },
    {
      key: "max_zoom",
      label: "Maximum Zoom",
      description:
        "Maximum zoom value of the camera. A value between 0.0 and 1.0 (will be adjusted based on the default ONVIF configuration). Automatically handled by the backend.",
      type: "float",
    },
  ],
};
