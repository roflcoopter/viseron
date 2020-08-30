# Viseron - Self-hosted NVR with object detection
Viseron is a self-hosted, local only NVR implemented in Python.
The goal is ease of use while also leveraging hardware acceleration for minimal system load.

# Notable features
- Records videos on detected objects
- Lookback, buffers frames to record before the event actually happened
- Multiplatform, should support any x86-64 machine running Linux, aswell as RPi3
Builds are tested and verified on the following platforms:
  - Ubuntu 18.04 with Nvidia GPU
  - Ubuntu 18.04 running on an Intel NUC
  - RaspberryPi 3B+

- Supports multiple different object detectors:
  - Yolo Darknet using OpenCV
  - Tensorflow via Google Coral EdgeTPU

- Supports hardware acceleration on different platforms
  - CUDA for systems with a supported GPU
  - OpenCL
  - OpenMax and MMAL on the RaspberryPi 3B+

# Getting started
Choose the appropriate docker container for your machine.
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
  Therefore i do not recommend using an RPi unless you have a Google Coral EdgeTPU.
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
## Camera
Used to build the FFMPEG command to decode camera stream.\
The command is built like this: \
```"ffmpeg" + global_args + input_args + hwaccel_args + codec + "-rtsp_transport tcp -i " + (stream url) + filter_args + output_args```
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| name | str | **required** | any string | Friendly name of the camera |
| mqtt_name | str | name given above | any string | Name used in MQTT topics |
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

## Object detection
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| type | str | RPi: ```edgetpu``` <br> Other: ```darknet``` | ```darknet```, ```edgetpu``` | What detection method to use.</br>Defaults to ```edgetpu``` on RPi. If no EdgeTPU is present it will run tensorflow on the CPU. |
| model_path | str | RPi: ```/detectors/models/edgetpu/model.tflite``` <br> Other: ```/detectors/models/darknet/yolo.weights``` | any valid path | Path to the object detection model |
| model_config | str | ```/detectors/models/darknet/yolo.cfg``` | any valid path | Path to the object detection config. Only needed for ```darknet``` |
| label_path | str | RPI: ```/detectors/models/edgetpu/labels.txt``` <br> Other: ```/detectors/models/darknet/coco.names``` | any valid path | Path to the file containing labels for the model |
| model_width | int | optional | any integer | Detected from model. Frames will be resized to this width in order to fit model and save computing power. I dont recommend changing this. |
| model_height | int | optional | any integer | Detected from model. Frames will be resized to this height in order to fit model and save computing power. I dont recommend changing this. |
| interval | float | 1.0 | any float | Run object detection at this interval in seconds. |
| threshold | float | 0.8 | float between 0 and 1 | Lowest confidence allowed for detected objects |
| suppression | float | 0.4 | float between 0 and 1 | Non-maxima suppression, used to remove overlapping detections |
| height_min | float | 0 | float between 0 and 1 | Minimum height allowed for detected objects, relative to stream height |
| height_max | float | 1 | float between 0 and 1 | Maximum height allowed for detected objects, relative to stream height |
| width_min | float | 0 | float between 0 and 1 | Minimum width allowed for detected objects, relative to stream width |
| width_max | float | 1 | float between 0 and 1 | Maximum width allowed for detected objects, relative to stream width |
| labels | list | ```person``` | any string | Can be any label present in the detection model |

## Motion detection
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| interval | float | 1.0 | any float | Run motion detection at this interval in seconds |
| trigger | bool | False | True/False | If true, detected motion will trigger object detector to start scanning |
| timeout | bool | False | True/False | If true, recording will continue until no motion is detected |
| width | int | 300 | any integer | Frames will be resized to this width in order to save computing power |
| height | int | 300 | any integer | Frames will be resized to this height in order to save computing power |
| area | int | 1000 | any integer | How big the detected area must be in order to trigger motion |
| frames | int | 1 | any integer | Number of consecutive frames with motion before triggering, used to reduce false positives |

TODO Future releases will make the motion detection easier to fine tune. Right now its a guessing game

## Recorder
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| lookback | int | 10 | any integer | Number of seconds to record before a detected object |
| timeout | int | 10 | any integer | Number of seconds to record after all events are over |
| retain | int | 7 | any integer | Number of days to save recordings before deleting them |
| folder | path | ```/recordings``` | What folder to store recordings in |
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
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| level | str | ```INFO``` | ```DEBUG```, ```INFO```, ```WARNING```, ```ERROR```, ```FATAL``` | Log level |

# Ideas and upcoming features
- UI
  - Create a UI for configuration and viewing of recordings

- Detectors
  - Pause detection via MQTT
  - Move detectors to specific folder
  - Allow specified confidence to override height/width thresholds
  - Refactor Darknet
  - Darknet Choose backend via config
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

- Decouple MQTT
  - One client object.
  - Start all camera threads, which need to expose an on_message function
  - Pass list of camera objects to MQTT

- Docker
  - Try to reduce container footprint

- Logger
  - Set loglevel individually for each component

https://devblogs.nvidia.com/object-detection-pipeline-gpus/
