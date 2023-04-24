---
title: Introduction
---

Viseron is a self-hosted, local only NVR implemented in Python.
The goal is ease of use while also leveraging hardware acceleration for minimal system load.

## Notable features

Viserons features include, but not limited to the following:

- Object detection via:
  - YOLOv3, YOLOv4 and YOLOv7 Darknet using OpenCV
  - Tensorflow via Google Coral EdgeTPU
  - [DeepStack](https://docs.deepstack.cc/)
- Motion detection
- Face recognition via:
  - dlib
  - [DeepStack](https://docs.deepstack.cc/)
  - [CompreFace](https://github.com/exadel-inc/CompreFace)
- Image classification
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

## Screenshots

<p align="center">
  Camera view
  <img src="/img/screenshots/Viseron-screenshot-cameras.png" alt-text="Camera view"/>
</p>

<p align="center">
  Recordings view
  <img src="/img/screenshots/Viseron-screenshot-recordings.png" alt-text="Recordings view"/>
</p>

<p align="center">
  Entities view
  <img src="/img/screenshots/Viseron-screenshot-entities.png" alt-text="Entities view"/>
</p>

<p align="center">
  Configuration Editor
  <img src="/img/screenshots/Viseron-screenshot-configuration.png" alt-text="Configuration Editor"/>
</p>
