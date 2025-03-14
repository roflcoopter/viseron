---
title: Introduction
---

Viseron is a self-hosted, local only NVR and AI Computer Vision software implemented in Python.

The goal of Viseron is to be easy to setup and use, while still being powerful and flexible. It is designed to be run on a local network, with no external dependencies, and no cloud services required.

## Notable features

Viserons features include, but not limited to the following:

- Continuous (24/7) recordings
- Tiered storage, allowing multiple storage media with different retention policies
- A timeline view of events
- Built in authentication system
- Object detection via:
  - YOLOv3, YOLOv4 and YOLOv7 Darknet using OpenCV
  - Tensorflow via [Google Coral EdgeTPU](https://coral.ai/)
  - [CodeProject.AI](https://www.codeproject.com/AI/index.aspx)
- Motion detection
- Face recognition via:
  - [CompreFace](https://github.com/exadel-inc/CompreFace)
  - [CodeProject.AI](https://www.codeproject.com/AI/index.aspx)
  - [dlib](http://dlib.net/)
- Image classification via:
  - Tensorflow via [Google Coral EdgeTPU](https://coral.ai/)
- License plate recognition via:
  - [CodeProject.AI](https://www.codeproject.com/AI/index.aspx)
- Responsive, mobile friendly Web UI written in TypeScript React
- MQTT support
- [Home Assistant](https://home-assistant.io) MQTT Discovery
- Lookback, record before an event actually happens
- Supports hardware acceleration on different platforms
  - CUDA for systems with a supported GPU
  - OpenCL
  - OpenMax and MMAL on the RaspberryPi 3B+
  - video4linux on the RaspberryPi 4
  - Intel QuickSync with VA-API
  - NVIDIA video4linux2 on Jetson Nano
- Multiplatform, should support any amd64, aarch64 or armhf machine running Linux.<br></br>
  Specific images are built to support:
  - RaspberryPi 3B+
  - RaspberryPi 4
  - NVIDIA Jetson Nano
- Zones to limit detection to a particular area to reduce false positives
- Masks to limit where object and motion detection occurs
- Stop/start cameras on-demand over MQTT
- Telegram support for notifications

## Screenshots

### Camera view

<img src="/img/screenshots/Viseron-screenshot-cameras.png" alt-text="Camera view"/>

### Recordings view

<img src="/img/screenshots/Viseron-screenshot-recordings.png" alt-text="Recordings view"/>

### Events view

<img src="/img/screenshots/Viseron-screenshot-events-events.png" alt-text="Events view"/>

### Timeline view

<img src="/img/screenshots/Viseron-screenshot-events-timeline.png" alt-text="Timeline view"/>

### Responsive camera grid for Events and Timeline

<img src="/img/screenshots/Viseron-Events-responsive-grid.gif" alt-text="Timeline view"/>

### Entities view

<img src="/img/screenshots/Viseron-screenshot-entities.png" alt-text="Entities view"/>

### Configuration Editor

<img src="/img/screenshots/Viseron-screenshot-configuration.png" alt-text="Configuration Editor"/>

## How does Viseron compare to other NVR software?

First of all, Viserons functionality is completely free and will always be free. There are no hidden costs or limitations.
This of course means that Viseron is not as feature rich as some of its alternatives, but it is constantly being improved and new features are added regularly.

Viseron is often compared to Frigate, and while they share some similarities, they are quite different in terms of features and implementation.
I have never used Frigate, so I cannot give a fair comparison, but my general advice is to try both and see which one you prefer.

Viseron has some built-in features that Frigate does not have, such as face recognition and license plate recognition.
Frigate on the other hand has some features that Viseron does not have, such as audio detection and object tracking.
