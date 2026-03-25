# Configuration

Viseron uses a YAML based configuration.

If no `/config/config.yaml` is found, a default one will be created for you on first start.<br />
The default configuration guides you through the basic setup, and should be a good starting point for most users.

You can edit the `config.yaml` in whatever way you like, but using the built in [Configuration Editor](/docs/documentation/configuration/edit_config) is simple way to get started.

## Example configuration

Below is an example configuration with publicly available cameras.

:::warning

This configuration serves as an example only.<br />
The cameras are not hosted by Viseron, and are not guaranteed to be online at all times.

Keep reading so you get a better understanding of how to configure Viseron for your own cameras.

:::

<details>
  <summary>
    Example configuration
  </summary>

```yaml title="/config/config.yaml"
ffmpeg:
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
```

</details>
