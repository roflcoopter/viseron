# Viseron - Self-hosted NVR with object detection
Viseron is a self-hosted, local only NVR implemented in Python.\
The goal is ease of use while also leveraging hardware acceleration for minimal system load.

# Notable features
- Records videos on detected objects
- Supports multiple different object detectors:
  - YOLOv3/4 Darknet using OpenCV
  - Tensorflow via Google Coral EdgeTPU
  - [DeepStack](https://docs.deepstack.cc/) 
- Motion detection
- Face recognition via:
  - dlib
  - [DeepStack](https://docs.deepstack.cc/) 
- Lookback, buffers frames to record before the event actually happened
- Multiarch Docker containers for ease of use.
- Supports hardware acceleration on different platforms
  - CUDA for systems with a supported GPU
  - OpenCL
  - OpenMax and MMAL on the RaspberryPi 3B+
  - video4linux on the RaspberryPi 4
  - Intel QuickSync with VA-API
  - NVIDIA video4linux2 on Jetson Nano
- Multiplatform, should support any amd64, aarch64 or armhf machine running Linux.\
  Specific images are built to support:
  - RaspberryPi 3B+
  - RaspberryPi 4
  - NVIDIA Jetson Nano

  Builds are tested and verified on the following platforms:
  - Ubuntu 18.04 with NVIDIA GPU
  - Ubuntu 18.04 running on an Intel NUC
  - RaspberryPi 3B+
- Native support for RTSP and MJPEG
- Zones to limit detection to a particular area to reduce false positives
- Masks to limit where motion detection occurs
- Stop/start cameras on-demand over MQTT
- Home Assistant integration via MQTT
- unRAID Community Application

# Table of Contents
- [Supported architectures](#supported-architectures)
- [Getting started](#getting-started)
- [Contributing](#contributing)
- [Configuration Options](#configuration-options)
  - [Cameras](#cameras)
    - [Substream](#substream)
    - [Camera motion detection](#camera-motion-detection)
    - [Camera object detection](#camera-object-detection)
    - [Mask](#mask)
    - [Zones](#zones)
    - [Points](#points)
    - [Static MJPEG streams](#static-mjpeg-streams)
  - [Object detection](#object-detection)
    - [Darknet](#darknet)
    - [EdgeTPU](#edgetpu)
    - [DeepStack](#deepstack-objects)
    - [Labels](#labels)
  - [Motion detection](#motion-detection)
    - [Background subtractor](#background-subtractor)
    - [Background subtractor MOG2](#background-subtractor-mog2)
  - [Recorder](#recorder)
  - [User Interface](#user-interface)
    - [Dynamic MJPEG streams](#dynamic-mjpeg-streams)
  - [Post Processors](#post-processors)
    - [Face Recognition](#face-recognition)
      - [dlib](#dlib)
      - [DeepStack](#deepstack-faces)
  - [MQTT](#mqtt)
    - [Topics for each camera](#topics-for-each-camera)
    - [Topics for each Viseron instance](#topics-for-each-viseron-instance)
    - [Home Assistant MQTT Discovery](#home-assistant-mqtt-discovery)
  - [Logger](#logger)
  - [Secrets](#secrets)
- [Benchmarks](#benchmarks)
- [User and Group Identifiers](#user-and-group-identifiers)

# Supported architectures
Viserons images support multiple architectures such as `amd64`, `aarch64` and `armhf`.\
Pulling `roflcoopter/viseorn:latest` should automatically pull the correct image for you.
An exception to this is if you have the need for a specific container, eg the CUDA version.\
Then you will need to specify your desired image.

The images available are:
| Image | Architecture | Description |
| ------------ | ----- | ----------- |
| `roflcoopter/viseron` | multiarch | Multiarch image |
| `roflcoopter/aarch64-viseron` | `aarch64` | Generic aarch64 image, with RPi4 hardware accelerated decoding/encoding |
| `roflcoopter/amd64-viseron` | `amd64` | Generic image |
| `roflcoopter/amd64-cuda-viseron` | `amd64` | Image with CUDA support |
| `roflcoopter/rpi3-viseron` | `armhf` | Built specifically for the RPi3 with hardware accelerated decoding/encoding |
| `roflcoopter/jetson-nano-viseron` | `aarch64` | Built specifically for the Jetson Nano with FFmpeg hardware accelerated deocoding and CUDA support |

---

# Getting started
Choose the appropriate docker container for your machine. Builds are published to [Docker Hub](https://hub.docker.com/repository/docker/roflcoopter/viseron)
<details>
<summary>On a RaspberryPi 3b+</summary>
  Example Docker command

  ```bash
  docker run --rm \
  --privileged \
  -v <recordings path>:/recordings \
  -v <config path>:/config \
  -v /etc/localtime:/etc/localtime:ro \
  -v /opt/vc/lib:/opt/vc/lib \
  --name viseron \
  --device /dev/vchiq:/dev/vchiq \
  --device /dev/vcsm:/dev/vcsm \
  --device /dev/bus/usb:/dev/bus/usb \
  roflcoopter/viseron:latest
  ```
  Example docker-compose
  ```yaml
  version: "2.4"
  services:
    viseron:
      image: roflcoopter/viseron:latest
      container_name: viseron
      volumes:
        - <recordings path>:/recordings
        - <config path>:/config
        - /etc/localtime:/etc/localtime:ro
        - /opt/vc/lib:/opt/vc/lib
      devices:
        - /dev/vchiq:/dev/vchiq
        - /dev/vcsm:/dev/vcsm
        - /dev/bus/usb:/dev/bus/usb
      privileged: true
  ```
  Note: Viseron is quite RAM intensive, mostly because of the object detection but also because of the lookback feature.\
  I do not recommend using an RPi unless you have a Google Coral EdgeTPU, the CPU is not fast enough and you might run out of memory.
  To make use of hardware accelerated decoding/encoding you might have to increase the allocated GPU memory.\
  To do this edit ```/boot/config.txt``` and set ```gpu_mem=256``` and then reboot.

  I also recommend configuring a [substream](#substream) if you plan on running Viseron on an RPi.
</details>

<details>
<summary>On a RaspberryPi 4</summary>
  Example Docker command

  ```bash
  docker run --rm \
  --privileged \
  -v <recordings path>:/recordings \
  -v <config path>:/config \
  -v /etc/localtime:/etc/localtime:ro \
  -v /dev/bus/usb:/dev/bus/usb \
  -v /opt/vc/lib:/opt/vc/lib \
  --name viseron \
  --device=/dev/video10:/dev/video10 \
  --device=/dev/video11:/dev/video11 \
  --device=/dev/video12:/dev/video12 \
  --device /dev/bus/usb:/dev/bus/usb \
  roflcoopter/viseron:latest
  ```
  Example docker-compose
  ```yaml
  version: "2.4"
  services:
    viseron:
      image: roflcoopter/viseron:latest
      container_name: viseron
      volumes:
        - <recordings path>:/recordings
        - <config path>:/config
        - /etc/localtime:/etc/localtime:ro
      devices:
        - /dev/video10:/dev/video10
        - /dev/video11:/dev/video11
        - /dev/video12:/dev/video12
        - /dev/bus/usb:/dev/bus/usb
      privileged: true
  ```
  Note: Viseron is quite RAM intensive, mostly because of the object detection but also because of the lookback feature.\
  I do not recommend using an RPi unless you have a Google Coral EdgeTPU, the CPU is not fast enough and you might run out of memory.
  To make use of hardware accelerated decoding/encoding you might have to increase the allocated GPU memory.\
  To do this edit ```/boot/config.txt``` and set ```gpu_mem=256``` and then reboot.

  I also recommend configuring a [substream](#substream) if you plan on running Viseron on an RPi.
</details>

<details>
  <summary>On a generic Linux machine</summary>

  Example Docker command

  ```bash
  docker run --rm \
  -v <recordings path>:/recordings \
  -v <config path>:/config \
  -v /etc/localtime:/etc/localtime:ro \
  --name viseron \
  roflcoopter/viseron:latest
  ```
  Example docker-compose
  ```yaml
  version: "2.4"

  services:
    viseron:
      image: roflcoopter/viseron:latest
      container_name: viseron
      volumes:
        - <recordings path>:/recordings
        - <config path>:/config
        - /etc/localtime:/etc/localtime:ro
  ```
</details>

<details>
  <summary>On a Linux machine with Intel CPU that supports VAAPI (Intel NUC for example)</summary>

  Example Docker command
  ```bash
  docker run --rm \
  -v <recordings path>:/recordings \
  -v <config path>:/config \
  -v /etc/localtime:/etc/localtime:ro \
  --name viseron \
  --device /dev/dri \
  roflcoopter/viseron:latest
  ```
  Example docker-compose
  ```yaml
  version: "2.4"

  services:
    viseron:
      image: roflcoopter/viseron:latest
      container_name: viseron
      volumes:
        - <recordings path>:/recordings
        - <config path>:/config
        - /etc/localtime:/etc/localtime:ro
      devices:
        - /dev/dri
  ```

</details>

<details>
  <summary>On a Linux machine with NVIDIA GPU</summary>

  Example Docker command
  ```bash
  docker run --rm \
  -v <recordings path>:/recordings \
  -v <config path>:/config \
  -v /etc/localtime:/etc/localtime:ro \
  --name viseron \
  --runtime=nvidia \
  roflcoopter/amd64-cuda-viseron:latest
  ```
  Example docker-compose
  ```yaml
  version: "2.4"

  services:
    viseron:
      image: roflcoopter/amd64-cuda-viseron:latest
      container_name: viseron
      volumes:
        - <recordings path>:/recordings
        - <config path>:/config
        - /etc/localtime:/etc/localtime:ro
      runtime: nvidia
  ```

</details>

<details>
  <summary>On a Jetson Nano</summary>

  Example Docker command
  ```bash
  docker run --rm \
  -v <recordings path>:/recordings \
  -v <config path>:/config \
  -v /etc/localtime:/etc/localtime:ro \
  --name viseron \
  --runtime=nvidia \
  --privileged \
  roflcoopter/jetson-nano-viseron:latest
  ```
  Example docker-compose
  ```yaml
  version: "2.4"

  services:
    viseron:
      image: roflcoopter/jetson-nano-viseron:latest
      container_name: viseron
      volumes:
        - <recordings path>:/recordings
        - <config path>:/config
        - /etc/localtime:/etc/localtime:ro
      runtime: nvidia
      privileged: true
  ```

  It is a must to run with `--privileged` so the container gets access to all the needed devices for hardware acceleration.\
  You can probably get around this by manually mounting all the needed devices but this is not something I have looked into.

</details>

</br>

VAAPI support is built into every `amd64` container. To utilize it you need to add ```--device /dev/dri``` to your docker command.\
EdgeTPU support is also included in all containers. To use it, add ```-v /dev/bus/usb:/dev/bus/usb --privileged``` to your docker command.

The ```config.yaml``` has to be mounted to the folder ```/config```.\
If no config is present, a default minimal one will be created.\
Here you need to fill in at least your cameras and you should be good to go.

# Contributing
Contributors to the project are very much appreciated.
See the [contribution guidelines](docs/CONTRIBUTING.md) on how to get started.

Some things you can help with:
- Implement an open feature request or issue from the [issue tracker](https://github.com/roflcoopter/viseron/issues)
- Improve the documentation
- Answer questions in issues or [discussions](https://github.com/roflcoopter/viseron/discussions)

You can also use the links below to sponsor Viseron or make a one time donation.

<a href="https://github.com/sponsors/roflcoopter" target="_blank"><img src="docs/img/sponsor_button.png" alt="Sponsor" style="height: 37px !important;width: 170px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5)" ></a>
<a href="https://www.buymeacoffee.com/roflcoopter" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 174px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a>

---

# Configuration Options
## Cameras

<details>
  <summary>Config example</summary>

  ```yaml
  cameras:
    - name: Front door
      mqtt_name: viseron_front_door
      host: 192.168.30.2
      port: 554
      username: user
      password: pass
      path: /Streaming/Channels/101/
      width: 1920
      height: 1080
      fps: 6 
      motion_detection:
        fps: 1
        trigger_detector: false
      object_detection:
        fps: 1
        labels:
          - label: person
            confidence: 0.9
          - label: pottedplant
            confidence: 0.9
  ```
</details>

Used to build the FFmpeg command to decode camera stream.\
The command is built like this: \
```"ffmpeg" + global_args + input_args + hwaccel_args + codec + "-rtsp_transport tcp -i " + (stream url) + filter_args + output_args```
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| name | str | **required** | any string | Friendly name of the camera |
| mqtt_name | str | name given above | any string | Name used in MQTT topics |
| stream_format | str | ```rtsp``` | ```rtsp```, ```rtmp```, ```mjpeg``` | FFmpeg stream format  |
| host | str | **required** | any string | IP or hostname of camera |
| port | int | **required** | any integer | Port for the camera stream |
| username | str | optional | any string | Username for the camera stream |
| password | str | optional | any string | Password for the camera stream |
| path | str | **optional** | any string | Path to the camera stream, eg ```/Streaming/Channels/101/``` |
| width | int | optional | any integer | Width of the stream. Will use FFprobe to get this information if not given, see [FFprobe stream information](#FFprobe-stream-information)  |
| height | int | optional | any integer | Height of the stream. Will use FFprobe to get this information if not given, see [FFprobe stream information](#FFprobe-stream-information)  |
| fps | int | optional | any integer | FPS of the stream. Will use FFprobe to get this information if not given, see [FFprobe stream information](#FFprobe-stream-information)  |
| global_args | list | optional | a valid list of FFmpeg arguments | See source code for default arguments |
| input_args | list | optional | a valid list of FFmpeg arguments | See source code for default arguments |
| hwaccel_args | list | optional | a valid list of FFmpeg arguments | FFmpeg decoder hardware acceleration arguments |
| codec | str | optional | any supported decoder codec | FFmpeg video decoder codec, eg ```h264_cuvid```<br>Will use FFprobe to get this information if not given, see [FFprobe stream information](#FFprobe-stream-information) |
| audio_codec | str | `copy` | any supported audio encoder codec | FFmpeg audio encoder codec for the generated segments, eg ```aac```.<br>Note that if you set this, FFmpeg will have to re-encode your stream which increases system load.<br>Will use FFprobe to get this information if not given, see [FFprobe stream information](#FFprobe-stream-information) |
| rtsp_transport | str | ```tcp``` | ```tcp```, ```udp```, ```udp_multicast```, ```http``` | Sets RTSP transport protocol. Change this if your camera doesn't support TCP |
| filter_args | list | optional | a valid list of FFmpeg arguments | See source code for default arguments |
| frame_timeout | int | 60 | any int | A timeout in seconds. If a frame has not been received in this time period FFmpeg will be restarted |
| pix_fmt | str | `nv12` | `nv12`, `yuv420p` | Only change this if the decoder you are using does not support `nv12`, as `nv12` is more efficient |
| substream | dictionary | optional | see [Substream config](#substream) | Substream to perform image processing on |
| motion_detection | dictionary | optional | see [Camera motion detection config](#camera-motion-detection) | Overrides the global ```motion_detection``` config |
| object_detection | dictionary | optional | see [Camera object detection config](#camera-object-detection) | Overrides the global ```object_detection``` config |
| zones | list | optional | see [Zones config](#zones) | Allows you to specify zones to further filter detections |
| publish_image | bool | false | true/false | If enabled, Viseron will publish an image to MQTT with drawn zones, objects, motion and masks.<br><b>Note: this will use some extra CPU and should probably only be used for debugging</b> |
| ffmpeg_loglevel | str | optional | ```quiet```, ```panic```, ```fatal```, ```error```, ```warning```, ```info```, ```verbose```, ```debug```, ```trace``` | Sets the loglevel for FFmpeg.<br> Should only be used in debugging purposes. |
| ffmpeg_recoverable_errors | list | optional | a list of strings | FFmpeg sometimes print errors that are not fatal.<br>If you get errors like ```Error starting decoder pipe!```, see below for details. |
| ffprobe_loglevel | str | optional | ```quiet```, ```panic```, ```fatal```, ```error```, ```warning```, ```info```, ```verbose```, ```debug```, ```trace``` | Sets the loglevel for FFprobe.<br> Should only be used in debugging purposes. |

#### Default FFmpeg decoder command
A default FFmpeg decoder command is generated, which varies a bit depending on the Docker container you use,
<details>
  <summary>For NVIDIA GPU support in the <b>roflcoopter/amd64-cuda-viseron</b> image</summary>

  ```
  ffmpeg -hide_banner -loglevel panic -avoid_negative_ts make_zero -fflags nobuffer -flags low_delay -strict experimental -fflags +genpts -stimeout 5000000 -use_wallclock_as_timestamps 1 -vsync 0 -c:v h264_cuvid -rtsp_transport tcp -i rtsp://<username>:<password>@<host>:<port><path> -f rawvideo -pix_fmt nv12 pipe:1
  ```
</details>

<details>
  <summary>For VAAPI support in the <b>roflcoopter/viseron</b> image</summary>

  ```
  ffmpeg -hide_banner -loglevel panic -avoid_negative_ts make_zero -fflags nobuffer -flags low_delay -strict experimental -fflags +genpts -stimeout 5000000 -use_wallclock_as_timestamps 1 -vsync 0 -hwaccel vaapi -vaapi_device /dev/dri/renderD128 -rtsp_transport tcp -i rtsp://<username>:<password>@<host>:<port><path> -f rawvideo -pix_fmt nv12 pipe:1
  ```
</details>

<details>
  <summary>For RPi3 in the <b>roflcoopter/rpi3-viseron</b> image</summary>

  ```
  ffmpeg -hide_banner -loglevel panic -avoid_negative_ts make_zero -fflags nobuffer -flags low_delay -strict experimental -fflags +genpts -stimeout 5000000 -use_wallclock_as_timestamps 1 -vsync 0 -c:v h264_mmal -rtsp_transport tcp -i rtsp://<username>:<password>@<host>:<port><path> -f rawvideo -pix_fmt nv12 pipe:1
  ```
</details>

This means that you do **not** have to set ```hwaccel_args``` *unless* you have a specific need to change the default command (say you need to change ```h264_cuvid``` to ```hevc_cuvid```)


#### FFmpeg recoverable errors
Sometimes FFmpeg prints errors which are not fatal, such as ```[h264 @ 0x55b1e115d400] error while decoding MB 0 12, bytestream 114567```.\
Viseron always performs a sanity check on the FFmpeg decoder command with ```-loglevel fatal```.\
If Viseron gets stuck on an error that you believe is **not** fatal, you can add a subset of that error to ```ffmpeg_recoverable_errors```. \
So to ignore the error above you would add this to your configuration:
```yaml
ffmpeg_recoverable_errors:
  - error while decoding MB
```

#### FFprobe stream information
Viseron needs to know the width, height, FPS and audio/video codecs of your stream.\
FFprobe is used on initialization to figure all this information out.

Some cameras dont play nice with this and fail to report some information.\
To circumvent this you can manually specify all these options.

If you specify all of `width`, `height`, `fps`, `codec` and `audio_codec`, Viseron will not need to call FFprobe and startup will be significantly faster.

---

### Substream
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| stream_format | str | ```rtsp``` | ```rtsp```, ```mjpeg``` | FFmpeg stream format |
| port | int | **required** | any integer | Port for the camera stream |
| path | str | **required** | any string | Path to the camera substream, eg ```/Streaming/Channels/102/``` |
| width | int | optional | any integer | Width of the stream. Will use FFprobe to get this information if not given |
| height | int | optional | any integer | Height of the stream. Will use FFprobe to get this information if not given |
| fps | int | optional | any integer | FPS of the stream. Will use FFprobe to get this information if not given |
| input_args | list | optional | a valid list of FFmpeg arguments | See source code for default arguments |
| hwaccel_args | list | optional | a valid list of FFmpeg arguments | FFmpeg decoder hardware acceleration arguments |
| codec | str | optional | any supported decoder codec | FFmpeg video decoder codec, eg ```h264_cuvid``` |
| audio_codec | str | `copy` | any supported audio encoder codec | FFmpeg audio encoder codec, eg ```aac```.<br>The only reason why you would set this on a substream is to speed up the initialization, see [FFprobe stream information](#FFprobe-stream-information) |
| rtsp_transport | str | ```tcp``` | ```tcp```, ```udp```, ```udp_multicast```, ```http``` | Sets RTSP transport protocol. Change this if your camera doesn't support TCP |
| filter_args | list | optional | a valid list of FFmpeg arguments | See source code for default arguments |
| frame_timeout | int | 30 | any int | A timeout in seconds. If a frame has not been received in this time period FFmpeg will be restarted |
| pix_fmt | str | `nv12` | `nv12`, `yuv420p` | Only change this if the decoder you are using does not support `nv12`, as `nv12` is more efficient |

Using the substream is a great way to reduce the system load from FFmpeg.\
When configured, two FFmpeg processes will spawn:\
\- One that reads the main stream and creates segments for recordings. Codec ```-c:v copy``` is used so practically no resources are used.\
\- One that reads the substream and pipes frames to Viseron for motion/object detection.

To really benefit from this you should reduce the framerate of the substream to match the lowest fps set for either motion or object detection.\
It may also be useful to change the resolution to something lower than the main stream.

---

### Camera motion detection
Refer to the global [motion detection config](#motion-detection).\
Note that you must use the same `type` for each camera.\
Each setting set here overrides the global [motion detection config](#motion-detection).

---

### Camera object detection
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| enable | bool | True | true/false | If set to false, object detection is disabled for this camera |
| fps | float | optional | any float | Run object detection at this FPS. Overrides global [config](#object-detection) |
| labels | list | optional | any float | A list of [labels](#labels). Overrides global [config](#labels). |
| mask | list | optional | see [Mask config](#mask) | Allows you to specify masks in the shape of polygons. <br>Use this to ignore objects in certain areas of the image |
| log_all_objects | bool | false | true/false | When set to true and loglevel is ```DEBUG```, **all** found objects will be logged. Can be quite noisy. Overrides global [config](#object-detection) |
| max_frame_age | float | 2 | any float larger than 0.0 | Drop frames that are older than this number, in seconds. Overrides global [config](#object-detection) |

---

### Mask

<details>
  <summary>Config example</summary>

  ```yaml
  cameras:
    - name: name
      host: ip
      port: port
      path: /Streaming/Channels/101/
      motion_detection:
        area: 0.07
        mask:
          - points:
              - x: 0
                y: 0
              - x: 250
                y: 0
              - x: 250
                y: 250
              - x: 0
                y: 250
          - points:
              - x: 500
                y: 500
              - x: 1000
                y: 500
              - x: 1000
                y: 750
              - x: 300
                y: 750
      object_detection:
        area: 0.07
        mask:
          - points:
              - x: 0
                y: 0
              - x: 250
                y: 0
              - x: 250
                y: 250
              - x: 0
                y: 250
          - points:
              - x: 400
                y: 200
              - x: 1000
                y: 200
              - x: 1000
                y: 750
              - x: 400
                y: 750
  ```
</details>

| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| points | list | **required** | a list of [points](#points) | Used to draw a polygon of the mask

Masks are used to exclude certain areas in the image from motion or object detection depending on the configuration.\
Say you have a camera which is filming some trees. When the wind is blowing, motion will probably be detected.\
Add a mask under the cameras `motion_detection` block that cover these trees and they will no longer trigger said motion.

To ignore all objects in a certain area, add a mask under the cameras `object_detection` block that covers the area.

---

### Zones

<details>
  <summary>Config example</summary>

  ```yaml
  cameras:
    - name: name
      host: ip
      port: port
      path: /Streaming/Channels/101/
      zones:
        - name: zone1
          points:
            - x: 0
              y: 500
            - x: 1920
              y: 500
            - x: 1920
              y: 1080
            - x: 0
              y: 1080
          labels:
            - label: person
              confidence: 0.9
        - name: zone2
          points:
            - x: 0
              y: 0
            - x: 500
              y: 0
            - x: 500
              y: 500
            - x: 0
              y: 500
          labels:
            - label: cat
              confidence: 0.5
  ```
</details>

| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| name | str | **required** | any str | Zone name, used in MQTT topic. Should be unique |
| points | list | **required** | a list of [points](#points) | Used to draw a polygon of the zone
| labels | list | optional | any float | A list of [labels](#labels) to track in the zone. Overrides global [config](#labels). | 

Zones are used to define areas in the cameras field of view where you want to look for certain objects(labels).

Say you have a camera facing the sidewalk and have ```labels``` setup to look for and record a ```person```.\
This would cause Viseron to start recording people who are walking past the camera on the sidewalk. Not ideal.\
To remedy this you define a zone which covers **only** the area that you are actually interested in, excluding the sidewalk.

---

### Points

| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| x | int | **required** | any int | X-coordinate of point |
| y | int | **required** | any int | Y-coordinate of point |

Points are used to form a polygon for a zone or a object/motion detection mask.

To easily generate points you can use a tool like [image-map.net](https://www.image-map.net/).\
Just upload an image from your camera and start drawing your zone.\
Then click **Show me the code!** and adapt it to the config format.\
Coordinates ```coords="522,11,729,275,333,603,171,97"``` should be turned into this:
```yaml
points:
  - x: 522
    y: 11
  - x: 729
    y: 275
  - x: 333
    y: 603
  - x: 171
    y: 97
```

---

### Static MJPEG Streams
<details>
  <summary>Config example</summary>

  ```yaml
  cameras:
    - name: Front door
      host: 192.168.30.2
      port: 554
      username: user
      password: pass
      path: /Streaming/Channels/101/
      static_mjpeg_streams:
        my-big-front-door-stream:
          width: 1920
          height: 1080
          draw_objects: True
        my-small-front-door-stream:
          width: 100
          height: 100
          draw_objects: True
  ```
</details>

| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| width | int | optional | any int | Frame will be rezied to this width. Required if height is set |
| height | int | optional | any int | Frame will be rezied to this height. Required if width is set |
| draw_objects | bool | optional | true/false | If set, found objects will be drawn |
| draw_motion | bool | optional | true/false | If set, detected motion will be drawn |
| draw_motion_mask | bool | optional | true/false | If set, configured motion masks will be drawn |
| draw_object_mask | bool | optional | true/false | If set, configured object masks will be drawn |
| draw_zones | bool | optional | true/false | If set, configured zones will be drawn |
| rotate | int | optional | any int | Degrees to rotate the image. Positive/negative values rotate clockwise/counter clockwise respectively |
| mirror | bool | optional | true/false | If set, mirror the image horizontally |

Viseron can serve predefined MJPEG streams.\
This is useful for debugging, but also if you want to view your camera on a Chromecast for instance.

The MJPEG streams work exactly as the [dynamic streams](#dynamic-mjpeg-streams) which uses query parameters.\
The benefit of using these predefined streams instead is that frame processing happens only once.\
This means that you can theoretically have as many streams open as you want without increased load on your machine.

The config example above would give you two streams, available at these endpoints:\
```http://localhost:8888/front_door/static-mjpeg-streams/my-big-front-door-stream```\
```http://localhost:8888/front_door/static-mjpeg-streams/my-small-front-door-stream```

## Object detection
<details>
  <summary>Config example</summary>

  ```yaml
  object_detection:
    type: darknet
    fps: 1
    labels:
      - label: person
        confidence: 0.9
        height_min: 0.1481
        height_max: 0.7
        width_min: 0.0598
        width_max: 0.36
      - label: truck
        confidence: 0.8
  ```
</details>

| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| enable | bool | True | true/false | If set to false, object detection is disabled |
| type | str | RPi: ```edgetpu``` <br> Other: ```darknet``` | ```darknet```, ```edgetpu```, ```deepstack``` | What detection method to use.<br>Each detector has its own configuration options explained here:<br>[darknet](#darknet)<br>[edgetpu](#edgetpu)<br>[deepstack](#deepstack-objects)|
| model_width | int | optional | any integer | Detected from model.<br>Frames will be resized to this width in order to fit model and save computing power.<br>I dont recommend changing this. |
| model_height | int | optional | any integer | Detected from model.<br>Frames will be resized to this height in order to fit model and save computing power.<br>I dont recommend changing this. |
| fps | float | 1.0 | any float | Run object detection at this FPS. |
| labels | list | optional | a list of [labels](#labels) | Global labels which applies to all cameras unless overridden |
| max_frame_age | float | 2 | any float larger than 0.0 | Drop frames that are older than this number, in seconds. Overrides global [config](#object-detection) |
| log_all_objects | bool | false | true/false | When set to true and loglevel is ```DEBUG```, **all** found objects will be logged. Can be quite noisy |

The above options are global for all types of detectors.\
If loglevel is set to ```DEBUG```, all detected objects will be printed in a statement like this:
<details>
  <summary>Debug log</summary>

  ```
[2020-09-29 07:57:23] [viseron.nvr.<camera name>.object ] [DEBUG   ] - Objects: [{'label': 'chair', 'confidence': 0.618, 'rel_width': 0.121, 'rel_height': 0.426, 'rel_x1': 0.615, 'rel_y1': 0.423, 'rel_x2': 0.736, 'rel_y2': 0.849}, {'label': 'pottedplant', 'confidence': 0.911, 'rel_width': 0.193, 'rel_height': 0.339, 'rel_x1': 0.805, 'rel_y1': 0.466, 'rel_x2': 0.998, 'rel_y2': 0.805}, {'label': 'pottedplant', 'confidence': 0.786, 'rel_width': 0.065, 'rel_height': 0.168, 'rel_x1': 0.522, 'rel_y1': 0.094, 'rel_x2': 0.587, 'rel_y2': 0.262}, {'label': 'pottedplant', 'confidence': 0.532, 'rel_width': 0.156, 'rel_height': 0.159, 'rel_x1': 0.644, 'rel_y1': 0.317, 'rel_x2': 0.8, 'rel_y2': 0.476}]
  ```
</details>

### Darknet
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| model_path | str | ```/detectors/models/darknet/yolo.weights``` | any valid path | Path to the object detection model |
| model_config | str | ```/detectors/models/darknet/yolo.cfg``` | any valid path | Path to the object detection config |
| label_path | str | ```/detectors/models/darknet/coco.names``` | any valid path | Path to the file containing labels for the model |
| suppression | float | 0.4 | float between 0 and 1 | Non-maxima suppression, used to remove overlapping detections.<br>You can read more about how this works [here](https://towardsdatascience.com/non-maximum-suppression-nms-93ce178e177c). |

The above options are specific to the ```type: darknet``` detector.
The included models are placed inside ```/detectors/models/darknet``` folder.\
The default model differs a bit per container:
- ```roflcoopter/viseron```: This one uses YOLOv3 by default.
- ```roflcoopter/amd64-viseron```: This one uses YOLOv3 by default.
- ```roflcoopter/amd64-cuda-viseron```: This one uses YOLOv4 by default.

The reason why not all containers are using YOLOv4 is that there are currently some issues with OpenCVs implementation of it.\
As soon as this is fixed for the versions of OpenCV that Viseron is using, YOLOv4 will be the standard for all.

The containers using YOLOv3 also has YOLOv3-tiny included in the image.\
YOLOv3-tiny can be used to reduce CPU usage, but will have **significantly** worse accuracy.
If you want to swap to YOLOv3-tiny you can change these configuration options:
  ```yaml
  object_detection:
    model_path: /detectors/models/darknet/yolov3-tiny.weights
    model_config: /detectors/models/darknet/yolov3-tiny.cfg
  ```

### EdgeTPU
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| model_path | str | ```/detectors/models/edgetpu/model.tflite``` | any valid path | Path to the object detection model |
| label_path | str | ```/detectors/models/edgetpu/labels.txt``` | any valid path | Path to the file containing labels for the model |
| device | str | `:0` | `:<N>` – use N-th EdgeTPU<br>`usb` – use any USB EdgeTPU<br>`usb:<N>` – use N-th USB EdgeTPU<br>`pci` – use any PCIe EdgeTPU<br>`pci:<N>` – use N-th PCIe EdgeTPU<br>`cpu` – use CPU instead of EdgeTPU | Which EdgeTPU to use.<br>Change this if you have multiple devices and want to use a specific one. |

The above options are specific to the ```type: edgetpu``` detector.\
The included models are placed inside ```/detectors/models/edgetpu``` folder.\
There are two models available, one that runs on the EdgeTPU and one the runs on the CPU.

---

### DeepStack Objects
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| host | str | **required** | any IP or hostname | IP address or hostname to your DeepStack server |
| port | int | **required** | any port | Port to your DeepStack server |
| image_width | int | optional | any int | Frames will be resized to this width to save computing power |
| image_height | int | optional | any int | Frames will be resized to this height to save computing power |
| custom_model | str | optional | any str | Name of a custom DeepStack model. More information [here](https://docs.deepstack.cc/custom-models/index.html) |
| api_key | str | optional | any str | API key to your DeepStack server, if you have set one |
| timeout | int | 10 | any port | Timeout for requests to your DeepStack server |

The above options are specific to the ```type: deepstack``` detector.

DeepStack is a self-hosted, free and open source AI server that provides, among other functions, object detection.\
It is highly optimized and runs on a pleathora of devices and platforms.\
Below is quoted from DeepStacks [documentation](https://docs.deepstack.cc/index.html):
> DeepStack is an AI server that empowers every developer in the world to easily build state-of-the-art AI systems both on premise and in the cloud. The promises of Artificial Intelligence are huge but becoming a machine learning engineer is hard. DeepStack is device and language agnostic. You can run it on Windows, Mac OS, Linux, Raspberry PI and use it with any programming language. \
DeepStack’s source code is available on GitHub via https://github.com/johnolafenwa/DeepStack\
DeepStack is developed and maintained by [DeepQuest AI](https://deepquestai.com/)

---

### Labels
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| label | str | person | any string | Can be any label present in the detection model |
| confidence | float | 0.8 | float between 0 and 1 | Lowest confidence allowed for detected objects.<br>The lower the value, the more sensitive the detector will be, and the risk of false positives will increase |
| height_min | float | 0 | float between 0 and 1 | Minimum height allowed for detected objects, relative to stream height |
| height_max | float | 1 | float between 0 and 1 | Maximum height allowed for detected objects, relative to stream height |
| width_min | float | 0 | float between 0 and 1 | Minimum width allowed for detected objects, relative to stream width |
| width_max | float | 1 | float between 0 and 1 | Maximum width allowed for detected objects, relative to stream width |
| trigger_recorder | bool | True | True/false | If set to True, objects matching this filter will start the recorder and signal over MQTT.<br> If set to False, only signal over MQTT will be sent |
| require_motion | bool | False | True/false | If set, the recorder will stop as soon as motion is no longer detected, even if the object still is. This is useful to avoid never ending recordings of stationary objects, such as a car on a driveway |
| post_processor | str | optional | any configured post processor | Send this detected object to the specified [post processor](#post-processors).

Labels are used to tell Viseron what objects to look for and keep recordings of.\
The available labels depends on what detection model you are using.\
For the built in models you can check the ```label_path``` file to see which labels that are available, see commands below.
<details>
  <summary>Darknet</summary>
  <code>docker exec -it viseron cat /detectors/models/darknet/coco.names</code>
</details>
<details>
  <summary>EdgeTPU</summary>
  <code>docker exec -it viseron cat /detectors/models/edgetpu/labels.txt</code>
</details>

The max/min width/height is used to filter out any unreasonably large/small objects to reduce false positives.\
Objects can also be filtered out with the use of an optional [mask](#mask).

**Important**: Viseron defaults to track `label: person`. This means that if you want not track any label at all you have to explicitly do so like this:
```yaml
object_detection:
  labels: []
```

---

## Motion detection
<details>
  <summary>Config example</summary>

  ```yaml
  motion_detection:
    fps: 1
    trigger_detector: true
    timeout: true
    max_timeout: 30
    width: 300
    height: 300
    area: 0.1
    frames: 3
  ```
</details>

| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| type | str | ```background_subtractor``` | ```background_subtractor```, ```mog2``` | What detection method to use.<br>Each detector has its own configuration options explained here:<br>[background_subtractor](#background-subtractor)<br>[mog2](#background-subtractor-mog2) |
| fps | float | 1.0 | any float | Run motion detection at this FPS. <br>For optimal performance, this should be divisible with the object detection fps, because then preprocessing will only occur once for each frame. |
| trigger_detector | bool | true | True/False | If true, the object detector will only run while motion is detected. |
| trigger_recorder | bool | true | True/False | If true, detected motion will start the recorder |
| timeout | bool | true | True/False | If true, recording will continue until no motion is detected |
| max_timeout | int | 30 | any integer | Value in seconds for how long motion is allowed to keep the recorder going when no objects are detected. <br>This is to prevent never-ending recordings. <br>Only applicable if ```timeout: true```.
| width | int | 300 | any integer | Frames will be resized to this width in order to save computing power |
| height | int | 300 | any integer | Frames will be resized to this height in order to save computing power |
| frames | int | 3 | any integer | Number of consecutive frames with motion before triggering, used to reduce false positives |

The above options are global for all types of motion detectors detectors.

---

### Background subtractor
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| area | float | 0.08| 0.0 - 1.0 | How big the detected area must be in order to trigger motion |
| threshold | int | 15 | 0 - 255 | The minimum allowed difference between our current frame and averaged frame for a given pixel to be considered motion. Smaller leads to higher sensitivity, larger values lead to lower sensitivity |
| alpha | float | 0.2 | 0.0 - 1.0 | How much the current image impacts the moving average.<br>Higher values impacts the average frame a lot and very small changes may trigger motion.<br>Lower value impacts the average less, and fast objects may not trigger motion. More can be read [here](https://docs.opencv.org/3.4/d7/df3/group__imgproc__motion.html#ga4f9552b541187f61f6818e8d2d826bc7). |

The above options are specific to the ```type: background_subtractor``` detector.\

Motion detection works by creating a running average of frames, and then comparing the current frame to this average.\
If enough changes have occurred, motion will be detected.\
By using a running average, the "background" image will adjust to daylight, stationary objects etc.\
[This](https://www.pyimagesearch.com/2015/06/01/home-surveillance-and-motion-detection-with-the-raspberry-pi-python-and-opencv/) blogpost from PyImageSearch explains this procedure quite well.

---

### Background subtractor MOG2
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| area | float | 0.08 | 0.0 - 1.0 | How big the detected area must be in order to trigger motion |
| threshold | int | 15 | 0 - 255 | The minimum allowed difference between our current frame and averaged frame for a given pixel to be considered motion. Smaller leads to higher sensitivity, larger values lead to lower sensitivity |
| history | int | 500 | any int | Length of the history |
| detect_shadows | bool | False | True/false | If True, shadows will be considered as motion. Enabling will also reduce speed by a little |
| learning_rate | float | 0.01 | 0.0 - 1.0 | How fast the background model learns. 0 means that the background model is not updated at all, 1 means that the background model is completely reinitialized from the last frame |

The above options are specific to the ```type: mog2``` detector.

Performs motion detection using the Background subtraction MOG2 algorithm.

---

## Recorder
<details>
  <summary>Config example</summary>

  ```yaml
  recorder:
    lookback: 10
    timeout: 10
    retain: 7
    folder: /recordings
  ```
</details>

| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| lookback | int | 10 | any integer | Number of seconds to record before a detected object |
| timeout | int | 10 | any integer | Number of seconds to record after all events are over |
| retain | int | 7 | any integer | Number of days to save recordings before deleting them |
| folder | path | ```/recordings``` | path to existing folder | What folder to store recordings in |
| filename_pattern | str | ```%H:%M:%S``` | strftime pattern | [strftime](https://strftime.org/) pattern for recordings.<br>Default pattern results in filenames like: `23:59:59.mp4` |
| segments_folder | path | ```/segments``` | any path | What folder to store FFmpeg segments in |
| extension | str | ```mp4``` | a valid video file extension | The file extension used for recordings. I don't recommend changing this |
| hwaccel_args | list | optional | a valid list of FFmpeg arguments | FFmpeg encoder hardware acceleration arguments |
| codec | str | `copy` | any supported encoder codec | FFmpeg video encoder codec, eg ```h264_nvenc``` |
| audio_codec | str | `copy` | any supported audio encoder codec | FFmpeg audio encoder codec, eg ```aac``` |
| filter_args | list | optional | a valid list of FFmpeg arguments | FFmpeg encoder filter arguments |
| thumbnail | dictionary | optional | see [Thumbnail](#thumbnail) | Options for the thumbnail created on start of a recording |

Viseron uses [FFmpeg segments](https://www.ffmpeg.org/ffmpeg-formats.html#segment_002c-stream_005fsegment_002c-ssegment) to handle recordings.\
This means Viseron will write small 5 second segments of the stream to disk, and in case of any recording starting, Viseron will find the appropriate segments and concatenate them together.\
The reason for using segments instead of just starting the recorder on an event, is to support to the ```lookback``` feature which makes it possible to record *before* an event actually happened.

<details>
  <summary>The default concatenation command</summary>

  ```
  ffmpeg -hide_banner -loglevel error -y -protocol_whitelist file,pipe -f concat -safe 0 -i - -c:v copy <outfile.mp4>
  ```
</details>

If you want to re-encode the video you can choose ```codec```, ```filter_args``` and optionally ```hwaccel_args```.\
To place the segments in memory instead of writing to disk, you can mount a tmpfs disk in the container.
<details>
  <summary>Example tmpfs configuration</summary>

  Example Docker command

  ```bash
  docker run --rm \
  -v <recordings path>:/recordings \
  -v <config path>:/config \
  -v /etc/localtime:/etc/localtime:ro \
  --tmpfs /tmp \
  --name viseron \
  roflcoopter/viseron:latest
  ```
  Example docker-compose
  ```yaml
  version: "2.4"

  services:
    viseron:
      image: roflcoopter/viseron:latest
      container_name: viseron
      volumes:
        - <recordings path>:/recordings
        - <config path>:/config
        - /etc/localtime:/etc/localtime:ro
      tmpfs:
        - /tmp
  ```
  config.yaml
  ```yaml
  recorder:
    segments_folder: /tmp
  ```
</details>

### Thumbnail
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| save_to_disk | boolean | False | True/False | If set to true, the thumbnail that is created on start of recording is saved to ```{folder}/{camera_name}/latest_thumbnail.jpg``` |
| filename_pattern | str | ```%H:%M:%S``` | strftime pattern | [strftime](https://strftime.org/) pattern for saved thumbnails.<br>Default pattern results in filenames like: `23:59:59.jpg` |
| send_to_mqtt | boolean | False | True/False | If set to true, the thumbnail that is created on start of recording is sent over MQTT. |

The default location for the thumbnail if ```save_to_disk: true``` is ```/recordings/{camera_name}/latest_thumbnail.jpg```

---

## User Interface
The user interface can be reached by default on port 8888 inside the container.

### Dynamic MJPEG Streams
Viseron will serve MJPEG streams of all cameras. \
The stream can be reached on a [slugified](https://github.com/un33k/python-slugify) version of the configured camera name with ```_``` as separator.\
If you are unsure on your camera name in this format you can run this snippet:\
```docker exec -it viseron python3 -c "from viseron.config import CONFIG; from viseron.helpers import print_slugs; print_slugs(CONFIG);"```

Example URL: ```http://localhost:8888/<camera name slug>/mjpeg-stream```

To increase performance it is recommended to use [static streams](#static-mjpeg-streams) instead. 

#### Query parameters
A number of query parameters are available to instruct Viseron to resize the stream or draw different things in the image.\
To utilize a parameter you append it to the URL after a ```?```. To add multiple parameters you separate them with ```&``` like this:\
```http://localhost:8888/<camera name slug>/mjpeg-stream?<parameter1>=<value>&<parameter2>=<value>```

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| width | int | frame will be resized to this width |
| height | int | frame will be resized to this height |
| draw_objects | any | If this query parameter is present, found objects will be drawn |
| draw_motion | any | If this query parameter is present, detected motion will be drawn |
| draw_motion_mask | any | If this query parameter is present, configured motion masks will be drawn |
| draw_zones | any | If this query parameter is present, configured zones will be drawn |
---

## Post Processors
<details>
  <summary>Config example</summary>

  ```yaml
  post_processors:
    face_recognition:
      type: dlib
      expire_after: 10
  ```
</details>

| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| face_recognition | dict | optional | see [Face Recognition](#face-recognition) | Configuration for face recognition. |

Post processors are used when you want to perform some kind of action when a specific object is detected.\
Right now the only implemented post processor is face recognition. In the future more of these post processors will be added (ALPR) along with the ability to create your own custom post processors.

### Face Recognition
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| type | str | ```dlib``` | ```dlib```, `deepstack` | What face recognition method to use.<br>Each recognizer has its own configuration options explained here:<br>[dlib](#dlib)<br>[deepstack](#deepstack-faces) |
| face_recognition_path | str | ```/config/face_recognition``` | path to folder | Path to folder which contains subdirectories with images for each face to track |
| expire_after | int | 5 | any int | Time in seconds before a detected face is no longer considered detected |
| save_unknown_faces | bool | True | True/False | If true, any unrecognized face will be saved to the folder specified in `unknown_faces_path`. You can then move this image to the folder of the correct person to improve accuracy |
| unknown_faces_path | str | ```/config/face_recognition/faces/unknown``` | path to folder | Path to folder where unknown faces will be stored |

On startup images are read from ```face_recognition_path``` and a model is trained to recognize these faces.\
The folder structure of the faces folder is very strict. Here is an example of the default one:
```
/config
|-- face_recognition
|   `-- faces
|       |-- person1
|       |   |-- image_of_person1_1.jpg
|       |   |-- image_of_person1_2.png
|       |   `-- image_of_person1_3.jpg
|       `-- person2
|       |   |-- image_of_person2_1.jpeg
|       |   `-- image_of_person2_2.jpg
```
The above options are global for all types of face recognition. 

#### **dlib**
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| model | str | CUDA: ```cnn```<br>Other: ```hog``` | ```cnn```, ```hog``` | Which face detection model to use.<br>```hog``` is less accurate but faster on CPUs.<br>```cnn``` is a more accurate deep-learning model which is GPU/CUDA accelerated (if available). |

The above options are specific to ```type: dlib``` face recognition.

#### **DeepStack Faces**
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| host | str | **required** | any IP or hostname | IP address or hostname to your DeepStack server |
| port | int | **required** | any port | Port to your DeepStack server |
| api_key | str | optional | any str | API key to your DeepStack server, if you have set one |
| timeout | int | 10 | any port | Timeout for requests to your DeepStack server |
| train | bool | True | True/False | If true, DeepStack will be trained on startup to recognize faces. If you already have DeepStack trained you can set this to false. |
| min_confidence | float | 0.5 | 0.0 - 1.0 | Discard any face with confidence lower than this value |

The above options are specific to ```type: deepstack``` face recognition.

DeepStack is a self-hosted, free and open source AI server that provides, among other functions, face recognition.\
It is highly optimized and runs on a pleathora of devices and platforms.\
Below is quoted from DeepStacks [documentation](https://docs.deepstack.cc/index.html):
> DeepStack is an AI server that empowers every developer in the world to easily build state-of-the-art AI systems both on premise and in the cloud. The promises of Artificial Intelligence are huge but becoming a machine learning engineer is hard. DeepStack is device and language agnostic. You can run it on Windows, Mac OS, Linux, Raspberry PI and use it with any programming language. \
DeepStack’s source code is available on GitHub via https://github.com/johnolafenwa/DeepStack\
DeepStack is developed and maintained by [DeepQuest AI](https://deepquestai.com/)


---

## MQTT
<details>
  <summary>Config example</summary>

  ```yaml
  mqtt:
    broker: mqtt_broker.lan
    port: 1883
    username: user
    password: pass
  ```
</details>

| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| broker | str | **required** | IP address or hostname | IP address or hostname of MQTT broker |
| port | int | 1883 | any integer | Port the broker is listening on |
| username | str | optional | any string | Username for the broker |
| password | str | optional | any string | Password for the broker |
| client_id | str | ```viseron``` | any string | Client ID used when connecting to broker |
| home_assistant | dict | optional | See [Home Assistant MQTT Discovery](#Home-Assistant-MQTT-Discovery) |  Home Assistant MQTT discovery. Enabled by default |
| last_will_topic | str | ```{client_id}/lwt``` | any valid MQTT topic | Last will topic


### Topics for each camera
<div style="margin-left: 1em;">

#### Camera status:
<div style="margin-left: 1em;">
<details>
  <summary>Topic: <b><code>{client_id}/{mqtt_name from camera config}/sensor/status/state</b></code></summary>
  <div style="margin-left: 1em;">
  A JSON formatted payload is published to this topic to indicate the current status of the camera

  ```json
  {"state": "scanning_for_objects", "attributes": {"last_recording_start": <timestamp>, "last_recording_end": <timestamp>}}
  ```

  Possible values in ```state```: ```recording/scanning_for_motion/scanning_for_objects```

  </div>
</details>
</details>
</div>

#### Camera control:
<div style="margin-left: 1em;">
<details>
  <summary>Topic: <b><code>{client_id}/{mqtt_name from camera config}/switch/set</b></code></summary>
  <div style="margin-left: 1em;">

  ```ON```: Turns camera on\
  ```OFF```: Turns camera off

  </div>
</details>
<details>
  <summary>Topic: <b><code>{client_id}/{mqtt_name from camera config}/switch/state</b></code></summary>
  <div style="margin-left: 1em;">
  A JSON formatted payload is published to this topic when a camera turns on/off.

  ```json
  {"state": "on", "attributes": {}}
  ```

  ```state```: on/off

  </div>
</details>
</div>

#### Images:
<div style="margin-left: 1em;">
<details>
  <summary>Topic: <b><code>{client_id}/{mqtt_name from camera config}/camera/image</b></code></summary>
  <div style="margin-left: 1em;">

  Images will be published with drawn objects, motion contours, zones and masks if ```publish_image: true``` is set in the config.\
  Objects that are discarded by a filter will have blue bounding boxes, while objects who pass the filter will be green.\
  Zones are drawn in red. If an object passes its filter and is inside the zone, the zone will turn green.\
  Motion contours that are smaller than configured ```area``` are drawn in dark purple, while bigger contours are drawn in pink.\
  Masks are drawn with an orange border and black background with 70% opacity.
  </div>
</details>
</div>

<div style="margin-left: 1em;">
<details>
  <summary>Topic: <b><code>{client_id}/{mqtt_name from camera config}/camera/latest_thumbnail/image</b></code></summary>
  <div style="margin-left: 1em;">

  An image is published to this topic on the start of a recording if ```send_to_mqtt``` under ```recorder``` is set to ```true```.\
  The image is the same as the thumbnail saved along with the recording.
  </div>
</details>
</div>

#### [Object detection](#camera-object-detection):
<div style="margin-left: 1em;">
<details>
  <summary>Topic: <b><code>{client_id}/{mqtt_name from camera config}/binary_sensor/object_detected/state</b></code></summary>
  <div style="margin-left: 1em;">
  A JSON formatted payload is published to this topic when <b>any</b> configured label is in the field of view.

  ```json
  {"state": "on", "attributes": {"objects": [{"label": "person", "confidence": 0.961, "rel_width": 0.196, "rel_height": 0.359, "rel_x1": 0.804, "rel_y1": 0.47, "rel_x2": 1.0, "rel_y2": 0.829}]}}
  ```

  ```state```: on/off\
  ```objects```: A list of all found objects that passes its filters
  </div>
</details>

<details>
  <summary>Topic: <b><code>{client_id}/{mqtt_name from camera config}/binary_sensor/object_detected_{label}/state</b></code></summary>
  <div style="margin-left: 1em;">
  A JSON formatted payload is published to this topic when a <b>specific</b> configured label is in the field of view.

  ```json
  {"state": "on", "attributes": {"count": 2}}
  ```
  ```state```: on/off\
  ```count```: The amount of the specific label found
  </div>
</details>
</div>

#### [Motion detection](#camera-motion-detection):
<div style="margin-left: 1em;">
<details>
  <summary>Topic: <b><code>{client_id}/{mqtt_name from camera config}/binary_sensor/motion_detected/state</b></code></summary>
  <div style="margin-left: 1em;">
  A JSON formatted payload is published to this topic when motion is detected.

  ```json
  {"state": "on", "attributes": {}}
  ```

  ```state```: on/off
  </div>
</details>
</div>

#### [Zones](#zones):
<div style="margin-left: 1em;">
<details>
  <summary>Topic: <b><code>{client_id}/{mqtt_name from camera config}/binary_sensor/{zone name}/state</b></code></summary>
  <div style="margin-left: 1em;">
  A JSON formatted payload is published to this topic when <b>any</b> configured label is in the specific zone.

  ```json
  {"state": "on", "attributes": {"objects": [{"label": "person", "confidence": 0.961, "rel_width": 0.196, "rel_height": 0.359, "rel_x1": 0.804, "rel_y1": 0.47, "rel_x2": 1.0, "rel_y2": 0.829}]}}
  ```

  ```state```: on/off\
  ```objects```: A list of all found objects that passes its filters
  </div>
</details>

<details>
  <summary>Topic: <b><code>{client_id}/{mqtt_name from camera config}/binary_sensor/{zone name}_{label}/state</b></code></summary>
  <div style="margin-left: 1em;">
  A JSON formatted payload is published to this topic when a <b>specific</b> configured label is in the specific zone.

  ```json
  {"state": "on", "attributes": {"count": 2}}
  ```
  ```state```: on/off\
  ```count```: The amount of the specific label found
  </div>
</details>
</div>
</div>


### Topics for each Viseron instance
<div style="margin-left: 1em;">

#### [Face recognition](#face-recognition)
<div style="margin-left: 1em;">
<details>
  <summary>Topic: <b><code>{client_id}/binary_sensor/face_detected{person name}/state</b></code></summary>
  <div style="margin-left: 1em;">
  A JSON formatted payload is published to this topic when a tracked face is detected.

  ```json
  {"state": "on", "attributes": {}}
  ```

  ```on``` will be published to this topic when the face is detected.\
  ```off``` will be published to this topic when the face has not been detected for ```expire_after``` seconds.

  </div>
</details>
</div>
</div>


All MQTT topics are largely inspired by Home Assistants way of organizing entities.

---

### Home Assistant MQTT Discovery
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| enable | bool | true | true/false | Enable or disable [Home Assistant MQTT discovery(https://www.home-assistant.io/docs/mqtt/discovery/)] |
| discovery_prefix | str | ```homeassistant``` | any string | [Discovery prefix](https://www.home-assistant.io/docs/mqtt/discovery/#discovery_prefix) |

Viseron integrates into Home Assistant using MQTT discovery and is enabled by default if you configure MQTT.\
Viseron will create a number of entities depending on your configuration.

**Cameras**\
A variable amount of cameras will be created based on your configuration.
1) A camera entity to debug zones, masks, objects and motion.\
   Images are only sent to this topic if ```publish_image: true```
2) If ```send_to_mqtt``` under ```recorder``` is set to ```true``` , a camera entity named ```camera.{client_id from mqtt config}_{mqtt_name from camera config}_latest_thumbnail``` is created

**Sensor**\
A sensor entity is created for each camera which indicates the status of Viseron.
The state is set to ```recording```, ```scanning_for_motion``` or ```scanning_for_objects``` depending on the situation.

**Binary Sensors**\
A variable amount of binary sensors will be created based on your configuration.
1) A binary sensor showing if any tracked object is in view.
2) A binary sensor for each tracked object showing if the label is in view.
3) A binary sensor for each zone showing if any tracked object is in the zone.
4) A binary sensor for each tracked object in a zone showing if the label is in the zone.
5) A binary sensor showing if motion is detected.
6) A binary sensor showing if a face is detected.

**Switch**\
A switch entity will be created for each camera.\
The switch is used to arm/disarm a camera. When disarmed, no system resources are used for the camera.

---

## Logger
<details>
  <summary>Config example</summary>

  ```yaml
  logger:
    default_level: debug
    logs:
      viseron.nvr: info
  ```
</details>

| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| default_level | str | ```INFO``` | ```DEBUG```, ```INFO```, ```WARNING```, ```ERROR```, ```FATAL``` | Log level |
| logs | dict | optional | True/False | Dictionary used to set log level for individual components. |

---

## Secrets
Any value in ```config.yaml``` can be substituted with secrets stored in ```secrets.yaml```.\
This can be used to remove any private information from your ```config.yaml``` to make it easier to share your ```config.yaml``` with others.

The ```secrets.yaml``` is expected to be in the same folder as ```config.yaml```.\
The full path needs to be ```/config/secrets.yaml```.

Here is a simple usage example.\
Contents of ```/config/secrets.yaml```:
```yaml
camera_ip: 192.168.1.2
username: coolusername
password: supersecretpassword
```
Contents of ```/config/config.yaml```:
```yaml
cameras:
  - name: Front Door
    host: !secret camera_ip
    username: !secret username
    password: !secret password
```

---

# User and Group Identifiers
When using volumes (`-v` flags) permissions issues can happen between the host and the container.
To solve this, you can specify the user `PUID` and group `PGID` as environment variables to the container.

<details>
  <summary>Docker command</summary>

  ```bash
  docker run --rm \
  -v <recordings path>:/recordings \
  -v <config path>:/config \
  -v /etc/localtime:/etc/localtime:ro \
  --name viseron \
  -e PUID=1000 \
  -e PGID=1000 \
  roflcoopter/viseron:latest
  ```
</details>
<details>
  <summary>Docker Compose</summary>

  Example docker-compose
  ```yaml
  version: "2.4"

  services:
    viseron:
      image: roflcoopter/viseron:latest
      container_name: viseron
      volumes:
        - <recordings path>:/recordings
        - <config path>:/config
        - /etc/localtime:/etc/localtime:ro
      environment:
        - PUID=1000
        - PGID=1000
  ```
</details>

Ensure the volumes are owned on the host by the user you specify.
In this example `PUID=1000` and `PGID=1000`.

To find the UID and GID of your current user you can run this command on the host:
```
  $ id your_username_here
```

Viseron runs as root (`PUID=0` and `PGID=0`) by default.\
This is because it can be problematic to get hardware acceleration and/or EdgeTPUs to work properly for everyone.\
The `s6-overlay` init scripts do a good job at fixing permissions for other users, but you may still face some issues if you choose to not run as root.\
If you do have issues, please open an issue and i will do my best to fix them.

---

# Benchmarks
Here I will show you the system load on a few different machines/configs.\
All examples are with one camera running 1920x1080 at 6 FPS.\
Motion and object detection running at 1 fps.

Intel i3-9350K CPU @ 4.00GHz 4 cores with NVIDIA GTX1660 Ti
| Process | Load on one core | When |
| -----   | -----| ---- |
| ffmpeg | ~5-6% | Continuously |
| viseron | ~1.3-3% | Scanning for motion only |
| viseron | ~7.6-9% | Scanning for objects only |
| viseron | ~8.6-9.3% | Scanning for motion and objects |

Intel NUC NUC7i5BNH (Intel i5-7260U CPU @ 2.20GHz 2 cores) using VAAPI and OpenCL
| Process | Load on one core | When |
| -----   | -----| ---- |
| ffmpeg | ~8% | Continuously |
| viseron | ~3.3% | Scanning for motion only |
| viseron | ~7.5% | Scanning for objects only |
| viseron | ~8% | Scanning for motion and objects |

Intel NUC NUC7i5BNH (Intel i5-7260U CPU @ 2.20GHz 2 cores) **without** VAAPI or OpenCL
| Process | Load on one core | When |
| -----   | -----| ---- |
| ffmpeg | ~25% | Continuously |
| viseron | ~3.3% | Scanning for motion only |
| viseron | ~23% | Scanning for objects only |
| viseron | ~24% | Scanning for motion and objects |

---

# Tips
- If you are experiencing issues with a camera, I suggest you add debug logging to it and examine the logs

---

# Ideas and upcoming features
- UI
  - Create a UI for configuration and viewing of recordings

- Detectors
  - Pause detection via MQTT
  - Allow specified confidence to override height/width thresholds
  - Dynamic detection interval, speed up interval when detection happens for all types of detectors
  - Implement an object tracker for detected objects
  - Make it easier to implement custom detectors

- Recorder
  - Weaving, If detection is triggered close to previous detection, send silent alarm and "weave" the videos together.
  - Dynamic lookback based on motion

https://devblogs.nvidia.com/object-detection-pipeline-gpus/

---
<a href="https://github.com/sponsors/roflcoopter" target="_blank"><img src="docs/img/sponsor_button.png" alt="Sponsor" style="height: 37px !important;width: 170px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5)" ></a>
<a href="https://www.buymeacoffee.com/roflcoopter" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 174px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a> \
Donations are very appreciated and will go directly into more hardware for Viseron to support.
