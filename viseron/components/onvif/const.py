"""ONVIF component constants."""

COMPONENT = "onvif"
DESC_COMPONENT = "ONVIF cameras integration."

# ONVIF CONFIG
CONFIG_CAMERAS = "cameras"
CONFIG_HOST = "host"
CONFIG_ONVIF_PORT = "port"
CONFIG_ONVIF_USERNAME = "username"
CONFIG_ONVIF_PASSWORD = "password"

CONFIG_ONVIF_TIMEOUT = "timeout"
CONFIG_ONVIF_USE_HTTPS = "use_https"
CONFIG_ONVIF_VERIFY_SSL = "verify_ssl"
CONFIG_ONVIF_WSDL_DIR = "wsdl_dir"
CONFIG_ONVIF_AUTO_CONFIG = "auto_config"

DEFAULT_ONVIF_TIMEOUT = 10
DEFAULT_ONVIF_USE_HTTPS = False
DEFAULT_ONVIF_VERIFY_SSL = True
DEFAULT_ONVIF_AUTO_CONFIG = True

"""
If all the service configurations below are filled in, then when Viseron starts up all
these configurations will be overridden to the ONVIF device and only if the auto_config
key is set to False. If auto_config is set to True, then all the service configurations
will be ignored and the existing configuration on the ONVIF device will be used.
"""

# ONVIF DEVICE CONFIG
CONFIG_DEVICE = "device"
CONFIG_DEVICE_HOSTNAME = "hostname"
CONFIG_DEVICE_DISCOVERABLE = "discoverable"
CONFIG_DEVICE_DATETIME_TYPE = "datetime_type"
DEVICE_DATETIME_TYPE_MAP = {"NTP", "Manual"}
CONFIG_DEVICE_DAYLIGHT_SAVINGS = "daylight_savings"
CONFIG_DEVICE_TIMEZONE = "timezone"
CONFIG_DEVICE_NTP_FROM_DHCP = "ntp_from_dhcp"
CONFIG_DEVICE_NTP_TYPE = "ntp_type"
DEVICE_NTP_TYPE_MAP = {"DNS", "IPv4", "IPv6"}
CONFIG_DEVICE_NTP_SERVER = "ntp_server"

# ONVIF IMAGING CONFIG
CONFIG_IMAGING = "imaging"
CONFIG_IMAGING_FORCE_PERSISTENCE = "force_persistence"
CONFIG_IMAGING_BRIGHTNESS = "brightness"
CONFIG_IMAGING_COLOR_SATURATION = "color_saturation"
CONFIG_IMAGING_CONTRAST = "contrast"
CONFIG_IMAGING_SHARPNESS = "sharpness"
CONFIG_IMAGING_IRCUT_FILTER = "ircut_filter"
IMAGING_IRCUT_FILTER_MAP = {"ON", "OFF", "AUTO"}
CONFIG_IMAGING_BACKLIGHT_COMPENSATION = "backlight_compensation"
IMAGING_BACKLIGHT_COMPENSATION_MAP = {"ON", "OFF"}
CONFIG_IMAGING_EXPOSURE = "exposure"
CONFIG_IMAGING_FOCUS = "focus"
CONFIG_IMAGING_WIDE_DYNAMIC_RANGE = "wide_dynamic_range"
CONFIG_IMAGING_WHITE_BALANCE = "white_balance"
CONFIG_IMAGING_IMAGE_STABILIZATION = "image_stabilization"
CONFIG_IMAGING_IRCUT_FILTER_AUTO_ADJUSTMENT = "ircut_filter_auto_adjustment"
CONFIG_IMAGING_TONE_COMPENSATION = "tone_compensation"
CONFIG_IMAGING_DEFOGGING = "defogging"
CONFIG_IMAGING_NOISE_REDUCTION = "noise_reduction"

DEFAULT_IMAGING_FORCE_PERSISTENCE = True

# ONVIF MEDIA CONFIG
CONFIG_MEDIA = "media"

# ONVIF PTZ CONFIG
CONFIG_PTZ = "ptz"
CONFIG_PTZ_HOME_POSITION = "home_position"
CONFIG_PTZ_REVERSE_PAN = "reverse_pan"
CONFIG_PTZ_REVERSE_TILT = "reverse_tilt"
CONFIG_PTZ_MIN_PAN = "min_pan"
CONFIG_PTZ_MAX_PAN = "max_pan"
CONFIG_PTZ_MIN_TILT = "min_tilt"
CONFIG_PTZ_MAX_TILT = "max_tilt"
CONFIG_PTZ_MIN_ZOOM = "min_zoom"
CONFIG_PTZ_MAX_ZOOM = "max_zoom"
CONFIG_PTZ_PRESETS = "presets"
CONFIG_PTZ_PRESET_NAME = "name"
CONFIG_PTZ_PRESET_PAN = "pan"
CONFIG_PTZ_PRESET_TILT = "tilt"
CONFIG_PTZ_PRESET_ZOOM = "zoom"
CONFIG_PTZ_PRESET_ON_STARTUP = "on_startup"

DEFAULT_PTZ_HOME_POSITION = False
DEFAULT_PTZ_REVERSE_PAN = False
DEFAULT_PTZ_REVERSE_TILT = False
DEFAULT_PTZ_PRESET_ON_STARTUP = False

# ONVIF CONFIG DESCRIPTIONS
DESC_CAMERAS = "List of ONVIF cameras to make available to the component."
DESC_ONVIF_PORT = "ONVIF port of the camera."
DESC_ONVIF_USERNAME = "ONVIF username for the camera."
DESC_ONVIF_PASSWORD = "ONVIF password for the camera."

DESC_ONVIF_TIMEOUT = "Timeout for ONVIF connections in seconds."
DESC_ONVIF_USE_HTTPS = "Use HTTPS for ONVIF connections."
DESC_ONVIF_VERIFY_SSL = "Verify SSL certificates for ONVIF connections."
DESC_ONVIF_WSDL_DIR = "Path to custom WSDL directory for ONVIF client."
DESC_ONVIF_AUTO_CONFIG = (
    "Set to <code>true</code> then it <b>will ignore all configuration</b> per each "
    "service and use the default service that is already on the ONVIF camera. Don't "
    "worry! This ONVIF component will automatically detect the existing "
    "configuration in the ONVIF camera precisely."
)

DESC_DEVICE = "Device service configuration."
DESC_DEVICE_HOSTNAME = "The hostname of the device."
DESC_DEVICE_DISCOVERABLE = (
    "Whether the device is discoverable on the network via WS-Discovery."
)

DESC_DEVICE_DATETIME_TYPE = "Defines if the date and time is set via NTP or manually."
DESC_DEVICE_DAYLIGHT_SAVINGS = "Indicates whether Daylight Savings Time is in effect."
DESC_DEVICE_TIMEZONE = (
    "The time zone in POSIX 1003.1 format. <b>Will be ignored</b> if the <code>"
    "datetime_type</code> key is set to <code>NTP</code>."
)
DESC_DEVICE_NTP_FROM_DHCP = (
    "Indicate if NTP address information is to be retrieved using DHCP."
)
DESC_DEVICE_NTP_TYPE = (
    "Network host type: IPv4, IPv6 or DNS. <b>Will be ignored</b> if the "
    "<code>ntp_from_dhcp</code> key is set to <code>true</code>. "
)
DESC_DEVICE_NTP_SERVER = (
    "The NTP server of the device, for example: <code>pool.ntp.org</code> or "
    "<code>time.google.com</code> or <code>192.168.1.1</code> (<b>must match</b> with "
    "<code>ntp_type</code>). <b>Will be ignored</b> if the <code>ntp_from_dhcp</code> "
    "key is set to <code>true</code>. "
)


DESC_MEDIA = "Media service configuration."


DESC_IMAGING = "Imaging service configuration."
DESC_IMAGING_FORCE_PERSISTENCE = (
    "To determine whether this setting will persist even after a device reboot."
)
DESC_IMAGING_BRIGHTNESS = "Brightness of the image (unit unspecified)."
DESC_IMAGING_COLOR_SATURATION = "Color Saturation of the image (unit unspecified)."
DESC_IMAGING_CONTRAST = "Contrast of the image (unit unspecified)."
DESC_IMAGING_SHARPNESS = "Sharpness of the Video image (unit unspecified)."
DESC_IMAGING_IRCUT_FILTER = "Infrared Cutoff Filter settings."
DESC_IMAGING_BACKLIGHT_COMPENSATION = (
    "Enabled/disabled Backlight Compensation mode (on/off)."
)
DESC_IMAGING_EXPOSURE = "Exposure mode of the device."
DESC_IMAGING_FOCUS = "Focus configuration."
DESC_IMAGING_WIDE_DYNAMIC_RANGE = "Wide dynamic range settings."
DESC_IMAGING_WHITE_BALANCE = "White balance settings."
DESC_IMAGING_IMAGE_STABILIZATION = (
    "Optional element to configure Image Stabilization feature."
)
DESC_IMAGING_IRCUT_FILTER_AUTO_ADJUSTMENT = (
    "An optional parameter applied to only auto mode to adjust timing of toggling "
    "Infrared Cutoff filter."
)
DESC_IMAGING_TONE_COMPENSATION = (
    "Optional element to configure Image Contrast Compensation."
)
DESC_IMAGING_DEFOGGING = "Optional element to configure Image Defogging."
DESC_IMAGING_NOISE_REDUCTION = "Optional element to configure Image Noise Reduction."


DESC_PTZ = "PTZ service configuration."
DESC_PTZ_HOME_POSITION = (
    "Move camera to home position on startup (<b>if supported by camera</b>). <b>Will "
    "be ignored</b> if any of the PTZ <code>presets</code> have the <code>on_startup"
    "</code> set to <code>true</code>."
)
DESC_PTZ_REVERSE_PAN = (
    "Reverse the pan direction. Will be implemented in backend and frontend, "
    "and <b>will not affect</b> the position of user defined PTZ <code>presets</code>."
)
DESC_PTZ_REVERSE_TILT = (
    "Reverse the tilt direction. Will be implemented in backend and frontend, "
    "and <b>will not affect</b> the position of user defined PTZ <code>presets</code>."
)
DESC_PTZ_MIN_PAN = (
    "Minimum pan value of the camera. A value between -1.0 and 1.0 (will be adjusted "
    "based on the default ONVIF configuration). Automatically handled by the backend."
)
DESC_PTZ_MAX_PAN = (
    "Maximum pan value of the camera. A value between -1.0 and 1.0 (will be adjusted "
    "based on the default ONVIF configuration). Automatically handled by the backend."
)
DESC_PTZ_MIN_TILT = (
    "Minimum tilt value of the camera. A value between -1.0 and 1.0 (will be adjusted "
    "based on the default ONVIF configuration). Automatically handled by the backend."
)
DESC_PTZ_MAX_TILT = (
    "Maximum tilt value of the camera. A value between -1.0 and 1.0 (will be adjusted "
    "based on the default ONVIF configuration). Automatically handled by the backend."
)
DESC_PTZ_MIN_ZOOM = (
    "Minimum zoom value of the camera. A value between -1.0 and 1.0 (will be adjusted "
    "based on the default ONVIF configuration). Automatically handled by the backend."
)
DESC_PTZ_MAX_ZOOM = (
    "Maximum zoom value of the camera. A value between -1.0 and 1.0 (will be adjusted "
    "based on the default ONVIF configuration). Automatically handled by the backend."
)
DESC_PTZ_PRESETS = (
    "A list of user-defined PTZ presets (using the <b>Absolute Move</b> operation <b>if"
    " supported by camera</b>). These presets <b>will not be saved</b> to the ONVIF "
    "camera."
)
DESC_PTZ_PRESET_NAME = "Name of the PTZ preset."
DESC_PTZ_PRESET_PAN = "Pan value of the PTZ preset. A value between -1.0 and 1.0."
DESC_PTZ_PRESET_TILT = "Tilt value of the PTZ preset. A value between -1.0 and 1.0."
DESC_PTZ_PRESET_ZOOM = "Zoom value of the PTZ preset. A value between -1.0 and 1.0"
DESC_PTZ_PRESET_ON_STARTUP = "Move to this (named) preset on startup."
