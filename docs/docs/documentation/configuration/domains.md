# Domains

Every component in Viseron implements one or more domains. A domain provides a set of capabilities such as object detection and motion detection.

In the following sections you will find a short description of each domain and its general capabilities.

## Camera domain

The `camera` domain is the base of it all.
This is the domain that connects to your camera and fetches frames for processing.
Each camera has a unique `camera identifier` which flows through the entire configuration.

:::info Camera identifier

A `camera identifier` is a so called slug in programming terms.
A slug is a human-readable unique identifier.

Valid characters are lowercase `a-z`, `0-9`, and underscores ( `_` ).

:::

[Link to all components with camera domain.](/components-explorer?tags=camera)

## Object Detector domain

The object detector domain scans for objects at requested intervals, sending events on detections for other parts of Viseron to consume.

:::info

Object detection can be configured to run all the time so you never miss anything, or only when there is detected motion, saving some resources.<br/>
Whatever floats your boat!
:::

[Link to all components with object detector domain.](/components-explorer?tags=object_detector)

## Motion Detector domain

The motion detector domain works in a similar way to the object detector.
When motion is detected, an event will be emitted and it will, if configured, start the object detector.

:::info

The motion detector can be configured to start recordings as well, bypassing the need for an object detector.

:::

[Link to all components with motion detector domain.](/components-explorer?tags=motion_detector)

## NVR domain

The NVR domain is what glues all the other domains together.
It handles:

- Fetches frames from the cameras
- Sends them to the detectors
- Starts and stops the recorder
- Sends frames to [post processors](#post-processors)

[Link to all components with NVR domain.](/components-explorer?tags=nvr)

## Post Processors

Post processors are used when you want to perform some kind of action when a specific object is detected.

In the future more of these post processors will be added along with the ability to create your own custom post processors.

If you have any ideas for a good post processor, please open an issue on [GitHub](https://github.com/roflcoopter/viseron/issues)

### Face Recognition domain

The face recognition domain is a post processor designed to recognise individuals in images.

[Link to all components with face recognition domain.](/components-explorer?tags=face_recognition)

### Image Classification domain

Image classification labels an entire image with a single label, in contrast to an object detector which labels multiple objects in an image.

Image classifiers generally support more specific detections than an object detector.
For instance, an object detector might be trained to detect the label birds, while an image classifier can be trained to detect multiple different species of birds.

[Link to all components with image classification domain.](/components-explorer?tags=image_classification)

### License Plate Recognition domain

The license plate recognition domain can detect car license plates and report their text.

[Link to all components with license plate recognition domain.](/components-explorer?tags=license_plate_recognition)
