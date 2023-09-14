---
toc_max_heading_level: 4
---

# Configuration

Viseron uses a YAML based configuration.

If no `/config/config.yaml` is found, a default one will be created for you.<br />
You need to fill this in order for Viseron to function. <br />

You can edit the `config.yaml` in whatever way you like, but using the built in Configuration Editor is recommended.

:::tip

The built in Configuration Editor has syntax highlighting, making your YAML endevours a bit easier.

<details>
  <summary>Demonstration of the Editor</summary>

<p align="center">
  <img src="/img/screenshots/Viseron-demo-configuration.gif" alt-text="Configuration Editor"/>
</p>

</details>

:::

## Example configuration

Below is an example configuration with publicly available cameras.

:::warning

This configuration serves as an example only.<br />
The cameras are not hosted by Viseron, and are not guaranteed to be online at all times.

Keep reading so you get a better understanding of how to configure Viseron for your own cameras.

:::

<details><summary>Example configuration</summary>

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
            trigger_recorder: true
      viseron_camera2:
        fps: 1
        labels:
          - label: person
            confidence: 0.8
            trigger_recorder: true
      viseron_camera3:
        fps: 1
        labels:
          - label: person
            confidence: 0.8
            trigger_recorder: true

nvr:
  viseron_camera:
  viseron_camera2:
  viseron_camera3:

webserver:

logger:
  default_level: debug
```

</details>

## Components

Viserons config consists of [components](/components-explorer).<br />
Every component provides different sets of domains (such as cameras, object detection, motion detection etc).<br />
These domains are then tied together, providing the full capabilities of Viseron.

Components generally implement at least one domain.<br />
:::info

You can mix and match components freely. For example you could use different object detectors for different cameras.

:::

## Domains

Below is a short description of each domain and its general capabilities.

### Camera domain

The `camera` domain is the base of it all.
This is the domain that connects to your camera and fetches frames for processing.
Each camera has a unique `camera identifier` which flows through the entire configuration.

:::info Camera identifier

A `camera identifier` is a so called slug in programming terms.
A slug is a human-readable unique identifier.

Valid characters are lowercase `a-z`, `0-9`, and underscores ( `_` ).

:::

[Link to all components with camera domain.](/components-explorer?tags=camera)

### Object Detector domain

The object detector domain scans for objects at requested intervals, sending events on detections for other parts of Viseron to consume.

:::info

Object detection can be configured to run all the time so you never miss anything, or only when there is detected motion, saving some resources.<br/>
Whatever floats your boat!
:::

[Link to all components with object detector domain.](/components-explorer?tags=object_detector)

### Motion Detector domain

The motion detector domain works in a similar way to the object detector.
When motion is detected, an event will be emitted and it will, if configured, start the object detector.

:::info

The motion detector can be configured to start recordings as well, bypassing the need for an object detector.

:::

[Link to all components with motion detector domain.](/components-explorer?tags=motion_detector)

### NVR domain

The NVR domain is what glues all the other domains together.
It handles:

- Fetches frames from the cameras
- Sends them to the detectors
- Starts and stops the recorder
- Sends frames to [post processors](#post-processors)

[Link to all components with NVR domain.](/components-explorer?tags=nvr)

### Post Processors

Post processors are used when you want to perform some kind of action when a specific object is detected.

In the future more of these post processors will be added along with the ability to create your own custom post processors.

If you have any ideas for a good post processor, please open an issue on [GitHub](https://github.com/roflcoopter/viseron/issues)

#### Face Recognition domain

The face recognition domain is a post processor designed to recognise individuals in images.

[Link to all components with face recognition domain.](/components-explorer?tags=face_recognition)

#### Image Classification domain

Image classification labels an entire image with a single label, in contrast to an object detector which labels multiple objects in an image.

Image classifiers generally support more specific detections than an object detector.
For instance, an object detector might be trained to detect the label birds, while an image classifier can be trained to detect multiple different species of birds.

[Link to all components with image classification domain.](/components-explorer?tags=image_classification)

#### License Plate Recognition domain

The license plate recognition domain can detect car license plates and report their text.

[Link to all components with license plate recognition domain.](/components-explorer?tags=license_plate_recognition)

## Secrets

Any value in `config.yaml` can be substituted with secrets stored in `secrets.yaml`.<br />
This can be used to remove any private information from your `config.yaml` to make it easier to share your `config.yaml` with others.

Here is a simple usage example.<br />

```yaml title="/config/secrets.yaml"
camera_one_host: 192.168.1.2
camera_one_username: coolusername
camera_one_password: supersecretpassword

camera_two_host: 192.168.1.3
camera_two_username: anotherusername
camera_two_password: moresecretpassword
```

```yaml title="/config/config.yaml"
ffmpeg:
  camera:
    camera_one:
      name: Camera 1
      host: !secret camera_one_host
      path: /Streaming/Channels/101/
      username: !secret camera_one_username
      password: !secret camera_one_password
    camera_two:
      name: Camera 2
      host: !secret camera_two_host
      path: /Streaming/Channels/101/
      username: !secret camera_two_username
      password: !secret camera_two_password
```

:::info

The `secrets.yaml` is expected to be in the same folder as `config.yaml`.<br />
The full path needs to be `/config/secrets.yaml`.

:::
