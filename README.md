# Viseron - Self-hosted NVR with object detection
Viseron is a self-hosted, local only NVR implemented in Python.
The goal is ease of use while also leveraging hardware acceleration for minimal system load.

# Notable features
- Records videos on detected objects
- Lookback, buffers frames to record before the event actually happened
- Multiplatform, should support any x86-64 machine running Linux, aswell as RPi3.\
Builds are tested and verified on the following platforms:
  - Ubuntu 18.04 with Nvidia GPU
  - Ubuntu 18.04 running on an Intel NUC
  - RaspberryPi 3B+
- Supports multiple different object detectors:
  - Yolo Darknet using OpenCV
  - Tensorflow via Google Coral EdgeTPU
- Motion detection
- Native support for RTSP and MJPEG
- Supports hardware acceleration on different platforms
  - CUDA for systems with a supported GPU
  - OpenCL
  - OpenMax and MMAL on the RaspberryPi 3B+
- Zones to limit detection to a particular area to reduce false positives
- Home Assistant integration via MQTT

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
  -v /dev/bus/usb:/dev/bus/usb \
  -v /opt/vc/lib:/opt/vc/lib \
  --name viseron \
  --device /dev/vchiq:/dev/vchiq --device /dev/vcsm:/dev/vcsm \
  roflcoopter/viseron-rpi:latest
  ```
  Example docker-compose
  ```yaml
  version: "2.4"
  services:
    viseron:
      image: roflcoopter/viseron-rpi:latest
      container_name: viseron
      volumes:
        - <recordings path>:/recordings
        - <config path>:/config
        - /etc/localtime:/etc/localtime:ro
        - /dev/bus/usb:/dev/bus/usb
        - /opt/vc/lib:/opt/vc/lib
      devices:
        - /dev/vchiq:/dev/vchiq
        - /dev/vcsm:/dev/vcsm
      privileged: true
  ```
  Note: Viseron is quite RAM intensive, mostly because of the object detection but also because of the lookback feature.\
  I do not recommend using an RPi unless you have a Google Coral EdgeTPU, the CPU is not fast enough and you might run out of memory.
  To make use of hardware accelerated decoding/encoding you might have to increase the allocated GPU memory.\
  To do this edit ```/boot/config.txt``` and set ```gpu_mem=256``` and then reboot.
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
  roflcoopter/viseron-vaapi:latest
  ```
  Example docker-compose
  ```yaml
  version: "2.4"

  services:
    viseron:
      image: roflcoopter/viseron-vaapi:latest
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
  <summary>On a Linux machine with Nvidia GPU</summary>

  Example Docker command
  ```bash
  docker run --rm \
  -v <recordings path>:/recordings \
  -v <config path>:/config \
  -v /etc/localtime:/etc/localtime:ro \
  --name viseron \
  --runtime=nvidia \
  roflcoopter/viseron-cuda:latest
  ```
  Example docker-compose
  ```yaml
  version: "2.4"

  services:
    viseron:
      image: roflcoopter/viseron-cuda:latest
      container_name: viseron
      volumes:
        - <recordings path>:/recordings
        - <config path>:/config
        - /etc/localtime:/etc/localtime:ro
      runtime: nvidia
  ```

</details>

VAAPI support is built into every container. To utilize it you need to add ```--device /dev/dri``` to your docker command.\
EdgeTPU support is also included in all containers. To use it, add ```-v /dev/bus/usb:/dev/bus/usb --privileged``` to your docker command.

The ```config.yaml``` has to be mounted to the folder ```/config```.\
If no config is present, a default minimal one will be created.\
Here you need to fill in atleast your cameras and you should be good to go.

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
        interval: 1
        trigger: false
      object_detection:
        interval: 1
        labels:
          - label: person
            confidence: 0.9
          - label: pottedplant
            confidence: 0.9
  ```
</details>

Used to build the FFMPEG command to decode camera stream.\
The command is built like this: \
```"ffmpeg" + global_args + input_args + hwaccel_args + codec + "-rtsp_transport tcp -i " + (stream url) + filter_args + output_args```
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| name | str | **required** | any string | Friendly name of the camera |
| mqtt_name | str | name given above | any string | Name used in MQTT topics |
| stream_format | str | ```rtsp``` | ```rtsp```, ```mjpeg``` | FFMPEG stream format  |
| host | str | **required** | any string | IP or hostname of camera |
| port | int | **required** | any integer | Port for the camera stream |
| username | str | optional | any string | Username for the camera stream |
| password | str | optional | any string | Password for the camera stream |
| path | str | optional | any string | Path to the camera stream, eg ```/Streaming/Channels/101/``` |
| width | int | detected from stream | any integer | Width of the stream. Will use OpenCV to get this information if not given |
| height | int | detected from stream | any integer | Height of the stream. Will use OpenCV to get this information if not given |
| fps | int | detected from stream | any integer | FPS of the stream. Will use OpenCV to get this information if not given |
| global_args | list | optional | a valid list of FFMPEG arguments | See source code for default arguments |
| input_args | list | optional | a valid list of FFMPEG arguments | See source code for default arguments |
| hwaccel_args | list | optional | a valid list of FFMPEG arguments | FFMPEG decoder hardware acceleration arguments |
| codec | str | optional | any supported decoder codec | FFMPEG video decoder codec, eg ```h264_cuvid``` |
| filter_args | list | optional | a valid list of FFMPEG arguments | See source code for default arguments |
| motion_detection | dictionary | optional | see [Motion detection config](#motion-detection) | Overrides the global ```motion_detection``` config |
| object_detection | dictionary | optional | see [Camera object detection config](#camera-object-detection) below | Overrides the global ```object_detection``` config |
| zones | list | optional | see [Zones config](#zones) below | Allows you to specify zones to further filter detections |
| publish_image | bool | false | true/false | If enabled, Viseron will publish an image to MQTT with drawn zones/objects |
| logging | dictionary | optional | see [Logging](#logging) | Overrides the global log settings for this camera |

The default command varies a bit depending on the supported hardware:
<details>
  <summary>For Nvidia GPU support</summary>

  ```
  ffmpeg -hide_banner -loglevel panic -avoid_negative_ts make_zero -fflags nobuffer -flags low_delay -strict experimental -fflags +genpts -stimeout 5000000 -use_wallclock_as_timestamps 1 -vsync 0 -c:v h264_cuvid -rtsp_transport tcp -i rtsp://<username>:<password>@<host>:<port><path> -f rawvideo -pix_fmt nv12 pipe:1
  ```
</details>

<details>
  <summary>For VAAPI support</summary>

  ```
  ffmpeg -hide_banner -loglevel panic -avoid_negative_ts make_zero -fflags nobuffer -flags low_delay -strict experimental -fflags +genpts -stimeout 5000000 -use_wallclock_as_timestamps 1 -vsync 0 -hwaccel vaapi -vaapi_device /dev/dri/renderD128 -rtsp_transport tcp -i rtsp://<username>:<password>@<host>:<port><path> -f rawvideo -pix_fmt nv12 pipe:1
  ```
</details>

<details>
  <summary>For RPi3</summary>

  ```
  ffmpeg -hide_banner -loglevel panic -avoid_negative_ts make_zero -fflags nobuffer -flags low_delay -strict experimental -fflags +genpts -stimeout 5000000 -use_wallclock_as_timestamps 1 -vsync 0 -c:v h264_mmal -rtsp_transport tcp -i rtsp://<username>:<password>@<host>:<port><path> -f rawvideo -pix_fmt nv12 pipe:1
  ```
</details>

### Camera object detection
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| interval | float | optional | any float | Run object detection at this interval in seconds. Overrides global [config](#object-detection) |
| labels | list | optional | any float | A list of [labels](#labels). Overrides global [config](#labels). | 

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
To easily genereate points you can use a tool like [image-map.net](https://www.image-map.net/).\
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

### Points
Points are used to form a polygon.
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| x | int | **required** | any int | X-coordinate of point |
| y | int | **required** | any int | Y-coordinate of point |

## Object detection
<details>
  <summary>Config example</summary>

  ```yaml
  object_detection:
    type: darknet
    interval: 6
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
| type | str | RPi: ```edgetpu``` <br> Other: ```darknet``` | ```darknet```, ```edgetpu``` | What detection method to use.</br>Defaults to ```edgetpu``` on RPi. If no EdgeTPU is present it will run tensorflow on the CPU. |
| model_path | str | RPi: ```/detectors/models/edgetpu/model.tflite``` <br> Other: ```/detectors/models/darknet/yolo.weights``` | any valid path | Path to the object detection model |
| model_config | str | ```/detectors/models/darknet/yolo.cfg``` | any valid path | Path to the object detection config. Only needed for ```darknet``` |
| label_path | str | RPI: ```/detectors/models/edgetpu/labels.txt``` <br> Other: ```/detectors/models/darknet/coco.names``` | any valid path | Path to the file containing labels for the model |
| model_width | int | optional | any integer | Detected from model. Frames will be resized to this width in order to fit model and save computing power. I dont recommend changing this. |
| model_height | int | optional | any integer | Detected from model. Frames will be resized to this height in order to fit model and save computing power. I dont recommend changing this. |
| interval | float | 1.0 | any float | Run object detection at this interval in seconds. |
| confidence | float | 0.8 | float between 0 and 1 | Lowest confidence allowed for detected objects |
| suppression | float | 0.4 | float between 0 and 1 | Non-maxima suppression, used to remove overlapping detections |
| labels | list | optional | a list of [labels](#labels) | Global labels which applies to all cameras unless overridden |
| logging | dictionary | optional | see [Logging](#logging) | Set the log level for the object detector |

### Labels
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| label | str | person | any string | 	Can be any label present in the detection model |
| height_min | float | 0 | float between 0 and 1 | Minimum height allowed for detected objects, relative to stream height |
| height_max | float | 1 | float between 0 and 1 | Maximum height allowed for detected objects, relative to stream height |
| width_min | float | 0 | float between 0 and 1 | Minimum width allowed for detected objects, relative to stream width |
| width_max | float | 1 | float between 0 and 1 | Maximum width allowed for detected objects, relative to stream width |


## Motion detection
<details>
  <summary>Config example</summary>

  ```yaml
  motion_detection:
    interval: 1
    trigger: true
    timeout: true
    width: 300
    height: 300
    area: 6000
    frames: 3
  ```
</details>

| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| interval | float | 1.0 | any float | Run motion detection at this interval in seconds |
| trigger | bool | False | True/False | If true, detected motion will trigger object detector to start scanning |
| timeout | bool | False | True/False | If true, recording will continue until no motion is detected |
| width | int | 300 | any integer | Frames will be resized to this width in order to save computing power |
| height | int | 300 | any integer | Frames will be resized to this height in order to save computing power |
| area | int | 6000 | any integer | How big the detected area must be in order to trigger motion |
| frames | int | 3 | any integer | Number of consecutive frames with motion before triggering, used to reduce false positives |
| logging | dictionary | optional | see [Logging](#logging) | Set the log level for the motion detector. Can be set for each camera individually. |

TODO Future releases will make the motion detection easier to fine tune. Right now its a guessing game

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
| extension | str | ```mp4``` | a valid video file extension | The file extension used for recordings. I don't recommend changing this |
| global_args | list | optional | a valid list of FFMPEG arguments | See source code for default arguments |
| hwaccel_args | list | optional | a valid list of FFMPEG arguments | FFMPEG encoder hardware acceleration arguments |
| codec | str | optional | any supported decoder codec | FFMPEG video encoder codec, eg ```h264_nvenc``` |
| filter_args | list | optional | a valid list of FFMPEG arguments | FFMPEG encoder filter arguments |

The default command varies a bit depending on the supported hardware:
<details>
  <summary>For Nvidia GPU support</summary>

  ```
  ffmpeg -hide_banner -loglevel panic -f rawvideo -pix_fmt nv12 -s:v <width>x<height> -r <fps> -i pipe:0 -y -c:v h264_nvenc <file>
  ```
</details>

<details>
  <summary>For VAAPI support</summary>

  ```
  ffmpeg -hide_banner -loglevel panic -hwaccel vaapi -vaapi_device /dev/dri/renderD128 -f rawvideo -pix_fmt nv12 -s:v <width>x<height> -r <fps> -i pipe:0 -y -c:v h264_vaapi -vf "format=nv12|vaapi,hwupload" <file>
  ```
</details>

<details>
  <summary>For RPi3</summary>

  ```
  ffmpeg -hide_banner -loglevel panic -f rawvideo -pix_fmt nv12 -s:v <width>x<height> -r <fps> -i pipe:0 -y -c:v h264_omx <file>
  ```
</details>

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
| broker | str | **required** | IP adress or hostname | IP adress or hostname of MQTT broker |
| port | int | 1883 | any integer | Port the broker is listening on |
| username | str | optional | any string | Username for the broker |
| password | str | optional | any string | Password for the broker |
| client_id | str | ```viseron``` | any string | Client ID used when connecting to broker |
| discovery_prefix | str | ```homeassistant``` | Used to configure sensors in Home Assistant |
| last_will_topic | str | ```{client_id}/lwt``` | Last will topic

## Logging
<details>
  <summary>Config example</summary>

  ```yaml
  logging:
    level: debug
  ```
</details>

| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| level | str | ```INFO``` | ```DEBUG```, ```INFO```, ```WARNING```, ```ERROR```, ```FATAL``` | Log level |

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

# Benchmarks
Here I will show you the system load on a few different machines/configs.\
All examples are with one camera running 1920x1080 at 6 FPS.\
Motion and object detection running at a 1 second interval.

Intel i3-9350K CPU @ 4.00GHz 4 cores with Nvidia GTX1660 Ti
| Process | Load on one core | When |
| -----   | -----| ---- |
| ffmpeg | ~5-6% | Continously |
| viseron | ~1.3-3% | Scanning for motion only |
| viseron | ~7.6-9% | Scanning for objects only |
| viseron | ~8.6-9.3% | Scanning for motion and objects |

Intel NUC NUC7i5BNH (Intel i5-7260U CPU @ 2.20GHz 2 cores) using VAAPI and OpenCL
| Process | Load on one core | When |
| -----   | -----| ---- |
| ffmpeg | ~8% | Continously |
| viseron | ~3.3% | Scanning for motion only |
| viseron | ~7.5% | Scanning for objects only |
| viseron | ~8% | Scanning for motion and objects |

Intel NUC NUC7i5BNH (Intel i5-7260U CPU @ 2.20GHz 2 cores) **without** VAAPI or OpenCL
| Process | Load on one core | When |
| -----   | -----| ---- |
| ffmpeg | ~25% | Continously |
| viseron | ~3.3% | Scanning for motion only |
| viseron | ~23% | Scanning for objects only |
| viseron | ~24% | Scanning for motion and objects |

# Home Assistant Integration
Viseron integrates into Home Assistant using MQTT discovery and is enabled by default if you configure MQTT.\
Viseron will create a number of entities depending on your configuration.

**Camera entity**\
A camera entity will be created for each camera\
Default state topic: ```homeassistant/camera/{mqtt_name from camera config}/image```\
Images will be published to this topic with drawn objects and zones.

**Binary Sensors**\
A variable amount of binary sensors will be created based on your configuration.
1) A binary sensor showing if any tracked object is in view.\
   Default state topic: ```homeassistant/binary_sensor/{mqtt_name from camera config}/state```
2) A binary sensor for each tracked object showing if the label is in view.\
   Default state topic: ```homeassistant/binary_sensor/{mqtt_name from camera config}/{label}/state```
3) A binary sensor for each zone showing if any tracked object is in the zone.\
   Default state topic: ```homeassistant/binary_sensor/{mqtt_name from camera config}/{zone}/state```
4) A binary sensor for each tracked object in a zone showing if the label is in the zone.\
   Default state topic: ```homeassistant/binary_sensor/{mqtt_name from camera config}/{zone}_{label}/state```

**Switch**\
A switch entity will be created for each camera.\
At the moment this does nothing but in the future it will be used to arm/disarm the camera.\
Default state topic: ```homeassistant/switch/{mqtt_name from camera config}/state```\
Default command topic: ```homeassistant/switch/{mqtt_name from camera config}/set```\

# Ideas and upcoming features
- UI
  - Create a UI for configuration and viewing of recordings

- Detectors
  - Pause detection via MQTT
  - Move detectors to specific folder
  - Allow specified confidence to override height/width thresholds
  - Dynamic detection interval, speed up interval when detection happens for all types of detectors
  - Implement an object tracker for detected objects
  - Make it easier to implement custom detectors

- Watchdog
  Build a watchdog for the camera process

- Recorder
  - Weaving, If detection is triggered close to previous detection, send silent alarm and "weave" the videos together.
  - Dynamic lookback based on motion

- Properties:
  All public vars should be exposed by property

- Docker
  - Try to reduce container footprint

- Logger
  - Set loglevel individually for each component

https://devblogs.nvidia.com/object-detection-pipeline-gpus/

---
<a href="https://www.buymeacoffee.com/roflcoopter" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 174px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a>
