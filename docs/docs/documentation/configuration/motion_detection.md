# Motion detection

Viseron has built-in motion detection capabilities that can analyze the video stream from your cameras to detect motion. This can be used to trigger object detectors, recordings and events.

[Link to all components with motion detection capabilities.](/components-explorer?tags=motion_detector)

## Trigger object detection

By setting the config option `scan_on_motion_only: true` in the object detector configuration, you can configure it to only run when motion is detected, reducing the load on your system.

:::tip

When using this option, make sure to tune the motion detector properly to avoid missing important detections.

:::

## Trigger event recording

You can also configure the motion detector to trigger recordings, bypassing the need for an object detector.

```yaml title="/config/config.yaml"
mog2: # Or any other component with motion detection
  motion_detector:
    cameras:
      camera_one:
        // highlight-start
        trigger_event_recording: true
        // highlight-end

```

## External motion detector

Viseron supports using an external motion detector to trigger recordings and events instead of using the motion detectors that analyze the video stream.

This can be useful if you have other methods of detecting motion that you want to utilize, such as a PIR sensor or similar.

### Supported triggers

Currently only MQTT is supported as a trigger for the external motion detector, but support for other methods like ONVIF or HTTP will be added in the future.

See the [MQTT documentation](/components-explorer/components/mqtt#motion-detection-trigger) for more information on how to set up MQTT in Viseron.
