# Viseron - Self-hosted NVR with object detection
Viseron is a self-hosted, local only NVR implemented in python.

# Notable features
- Records videos on detected objects
- Lookback, buffers frames to record before the event actually happened
- Multiplatform, should support most linux based machines.\
Builds are verified on the following platforms:
  - Ubuntu 18.04 with Nvidia GPU
  - Ubuntu 18.04 running on an Intel NUC
  - RaspberryPi 3B+

- Supports multiple different object detectors, including but not limited to:
  - Yolo Darknet using OpenCV
  - Google Coral EdgeTPU

- Supports hardware acceleration on different platforms
  - CUDA for systems with a supported GPU
  - OpenCL
  - OpenMax and MMAL on the RaspberryPi 3B+

# Getting started
Choose the appropriate docker container for your machine.\
On a RaspberryPi 3b+:\
```TODO INSERT DOCKER COMMAND HERE```\
Viseron is quite RAM intensive, mostly because of the object detection but also because of the lookback feature.\
Therefore i do not recommend using an RPi unless you have a Google Coral EdgeTPU.

On a generic linux machine:\
```TODO INSERT DOCKER COMMAND HERE ```

On a generic linux machine with Intel CPU that supports ```vaapi```:\
```TODO INSERT DOCKER COMMAND HERE ```

On a Linux machine with Nvidia GPU:\
```TODO INSERT DOCKER COMMAND HERE ```

The ```config.yaml``` has to be mounted to the folder ```/config```.\
If no config is present, a default minimal one will be created.\
Here you need to fill in atleast your cameras and you should be good to go.
TODO CREATE DEFAULT CONFIG

# Configuration Options
## Camera
Used to build the FFMPEG command to decode camera stream.\
The command is built like this: \
```"ffmpeg" + global_args + input_args + hwaccel_args + "-rtsp_transport tcp -i " + (stream url) + filter_args + output_args```
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
| filter_args | list | optional | a valid list of FFMPEG arguments | See source code for default arguments |
TODO INSERT DEFAULT COMMAND HERE IN SPOILER TAG

## Object detection
TODO this config has to be simplified and use a default config to ease use
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| type | str | ```darknet``` | ```darknet```, ```edgetpu``` , ```posenet``` | What detection method to use |
| model_path | str | ```/detectors/models/darknet/yolov.weights``` | any valid path | Path to the object detection model |
| model_config | str | ```/detectors/models/darknet/yolov.cfg``` | any valid path | Path to the object detection config |
| label_path | str | ```/detectors/models/darknet/coco.names``` | any valid path | Path to the file containing labels for the model |
| model_width | int | 320 | any integer | Frames will be resized to this width in order to fit model and save computing power |
| model_height | int | 320 | any integer | Frames will be resized to this height in order to fit model and save computing power |
| interval | int | 1 | any integer | Run detection every nth frame.</br>1 = every frame</br>2 = every other frame</br>3 = every third frame</br>etc |
| threshold | float | 0.9 | float between 0 and 1 | Lowest confidence allowed for detected objects |
| suppression | float | 0.4 | float between 0 and 1 | Non-maxima suppression, used to remove overlapping detections |
| height_min | float | 0 | float between 0 and 1 | Minimum height allowed for detected objects, relative to stream height |
| height_max | float | 1 | float between 0 and 1 | Maximum height allowed for detected objects, relative to stream height |
| width_min | float | 0 | float between 0 and 1 | Minimum width allowed for detected objects, relative to stream width |
| width_max | float | 1 | float between 0 and 1 | Maximum width allowed for detected objects, relative to stream width |
| labels | list | ```person``` | any string | Can be any label present in the detection model |

## Motion detection
TODO Width height and area need to relative just like object detector
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| interval | int | 0 | any integer | Run motion detection every nth frame.</br>1 = every frame</br>2 = every other frame</br>3 = every third frame</br>etc |
| trigger | bool | False | True/False | If true, detected motion will trigger object detector to start scanning |
| timeout | bool | False | True/False | If true, recording will continue until no motion is detected |
| width | int | 300 | any integer | Frames will be resized to this width in order to save computing power |
| height | int | 300 | any integer | Frames will be resized to this height in order to save computing power |
| area | int | 1000 | any integer | How big the detected area must be in order to trigger motion |
| frames | int | 1 | any integer | Number of consecutive frames with motion before triggering, used to reduce false positives |

## Recorder
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
lookback | int | 10 | any integer | Number of seconds to record before a detected object |
timeout | int | 10 | any integer | Number of seconds to record after all events are over |
retain | int | 7 | any integer | Number of days to save recordings before deleting them |
folder | path | ```/recordings``` | What folder to store recordings in |
extension | str | ```mp4``` | a valid video file extension | The file extension used for recordings. I don't recommend changing this |
| global_args | list | optional | a valid list of FFMPEG arguments | See source code for default arguments |
| hwaccel_args | list | optional | a valid list of FFMPEG arguments | FFMPEG encoder hardware acceleration arguments |
| output_args | list | optional | a valid list of FFMPEG arguments | See source code for default arguments |

## MQTT
| Name | Type | Default | Supported options | Description |
| -----| -----| ------- | ----------------- |------------ |
| broker | str | **required** | IP adress or hostname | IP adress or hostname of MQTT broker |
| port | int | 1883 | any integer | Port the broker is listening on |
| username | str | optional | any string | Username for the broker |
| password | str | optional | any string | Password for the broker |
| client_id | str | ```viseron``` | any string | Client ID used when connecting to broker |
| discovery_prefix | str | ```homeassistant``` | Used to configure sensors in Home Assistant |
| last_will_topic | str | ```viseron/lwt``` | Last will topic


# Ideas and upcoming features
- UI
  - Create a UI for configuration and viewing of recordings

- Detectors
  - Move detectors to specific folder
  - Allow specified confidence to override height/width thresholds
  - Refactor Darknet
  - Darknet Choose backend via config
  - Dynamic detection interval, speed up interval when detection happens for all types of detectors
  - Implement an object tracker for detected objects

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
