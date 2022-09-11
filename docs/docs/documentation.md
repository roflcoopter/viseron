---
title: Documentation
---

# Viseron

Viseron is a self-hosted, local only NVR implemented in Python.
The goal is ease of use while also leveraging hardware acceleration for minimal system load.

# Notable features

Viserons features include, but not limited to the following:

- Object detection via:
  - YOLOv3/4 Darknet using OpenCV
  - Tensorflow via Google Coral EdgeTPU
  - [DeepStack](https://docs.deepstack.cc/)
- Motion detection
- Face recognition via:
  - dlib
  - [DeepStack](https://docs.deepstack.cc/)
- Responsive, mobile friendly Web UI using React
- MQTT support
- [Home Assistant](https://home-assistant.io) MQTT Discovery
- Lookback, buffers frames to record before the event actually happened
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
