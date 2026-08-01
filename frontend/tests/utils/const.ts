// Same config as in the docs
export const DEFAULT_YAML_CONFIG = `ffmpeg:
  camera:
    viseron_camera:
      name: Camera 1
      host: 195.196.36.242
      path: /mjpg/video.mjpg
      port: 80
      stream_format: mjpeg
      fps: 6
      recorder:
        idle_timeout: 1
        codec: h264
    viseron_camera2:
      name: Camera 2
      host: storatorg.halmstad.se
      path: /mjpg/video.mjpg
      stream_format: mjpeg
      port: 443
      fps: 2
      protocol: https
      recorder:
        idle_timeout: 1
        codec: h264
    viseron_camera3:
      name: Camera 3
      host: 195.196.36.242
      path: /mjpg/video.mjpg
      port: 80
      stream_format: mjpeg
      fps: 6
      recorder:
        idle_timeout: 1
        codec: h264

mog2:
  motion_detector:
    cameras:
      viseron_camera:
        fps: 1
      viseron_camera2:
        fps: 1

background_subtractor:
  motion_detector:
    cameras:
      viseron_camera3:
        fps: 1
        mask:
          - coordinates:
              - x: 400
                y: 200
              - x: 1000
                y: 200
              - x: 1000
                y: 750
              - x: 400
                y: 750

darknet:
  object_detector:
    cameras:
      viseron_camera:
        fps: 1
        scan_on_motion_only: false
        labels:
          - label: person
            confidence: 0.8
            trigger_event_recording: true
      viseron_camera2:
        fps: 1
        labels:
          - label: person
            confidence: 0.8
            trigger_event_recording: true
      viseron_camera3:
        fps: 1
        labels:
          - label: person
            confidence: 0.8
            trigger_event_recording: true

nvr:
  viseron_camera:
  viseron_camera2:
  viseron_camera3:

webserver:

logger:
  default_level: debug
`;

// Example setup-status errors covering different source types.
export const MOCK_SETUP_STATUS_COMPONENTS = [
  {
    name: "ffmpeg",
    state: "failed",
    errors: [],
    validation_error:
      "required key not provided @ data['ffmpeg']['camera']['viseron_camera']['host']",
    domains: [],
  },
  {
    name: "darknet",
    state: "failed",
    errors: [
      {
        source: "import",
        message: "Failed to import component 'darknet': No module named 'cv2'",
        component_name: "darknet",
      },
    ],
    validation_error: null,
    domains: [],
  },
  {
    name: "mqtt",
    state: "failed",
    errors: [
      {
        source: "setup",
        message:
          "Failed to connect to MQTT broker at 192.168.1.10:1883: Connection refused",
        component_name: "mqtt",
      },
    ],
    validation_error: null,
    domains: [],
  },
  {
    name: "codeprojectai",
    state: "failed",
    errors: [
      {
        source: "setup_domains",
        message:
          "Failed to set up domain 'object_detector' for identifier 'viseron_camera'",
        component_name: "codeprojectai",
        domain: "object_detector",
        identifier: "viseron_camera",
      },
    ],
    validation_error: null,
    domains: [],
  },
  {
    name: "compreface",
    state: "failed",
    errors: [
      {
        source: "domain",
        message:
          "Domain 'face_recognition' for identifier 'viseron_camera' failed to set up, retrying in 30 seconds",
        component_name: "compreface",
        domain: "face_recognition",
        identifier: "viseron_camera",
      },
    ],
    validation_error: null,
    domains: [],
  },
];
