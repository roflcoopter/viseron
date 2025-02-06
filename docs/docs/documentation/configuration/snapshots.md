# Snapshots

Snapshots are images taken when events are triggered or when a post processor finds anything. Snapshots will be taken for object detection, motion detection, and any post processor that scans the image, for example face and license plate recognition.

The snapshots are saved to disk and can be viewed in the web interface on the `Events` and `Timeline` tab on the `Events` page.

## Object detector snapshots

Snapshots are stored based on the `store` option under `label` in the object detector configuration.
When set to `true` (which is the default), a snapshot will be stored when the label is detected.

The `store_interval` option can be used to limit the number of snapshots stored. The snapshot will only be stored if the time since the last snapshot is greater than the `store_interval`.

```yaml
codeprojectai:
  host: cpai.lan
  port: 32168
  object_detector:
    cameras:
      camera_one:
        fps: 1
        scan_on_motion_only: false
        labels:
          - label: person
            confidence: 0.8
            trigger_event_recording: true
            // highlight-start
            store: true
            store_interval: 300 # Only store a snapshot of this label every 300 seconds
            // highlight-end
```

:::warning

Stationary objects can trigger a lot of snapshots. Be careful with the `store_interval` option to avoid filling up your disk.
[Retention rules](#retention-rules) can be used to make sure that not too many snapshots are stored.

In the future object tracking will be implemented to avoid this issue.

:::

## Motion detector snapshots

Snapshots are stored every time motion is detected. Another snapshot will not be stored until the motion has stopped and started again.

## Face recognition snapshots

Snapshots are stored based on the `save_faces` option in the face recognition configuration.
When set to `true` (which is the default), a snapshot will be stored when a face is detected.

`save_unknown_faces` can be used to store snapshots of unknown faces.

A snapshot will only be stored once for each face until the face is not detected for a certain amount of time. This time can be set with the `expire_after` option.

```yaml
codeprojectai:
  host: cpai.lan
  port: 32168
  face_recognition:
    // highlight-start
    save_faces: true
    save_unknown_faces: true
    expire_after: 10
    // highlight-end
    cameras:
      camera_one:
    labels:
      - person
```

## License plate recognition snapshots

Snapshots are stored based on the `save_plates` option in the license plate recognition configuration.
When set to `true` (which is the default), a snapshot will be stored when a license plate is detected.

Just like with face recognition, a snapshot will only be stored once for each license plate until the license plate is not detected for a certain amount of time. This time can be set with the `expire_after` option.

```yaml
codeprojectai:
  host: cpai.lan
  port: 32168
  license_plate_recognition:
    // highlight-start
    save_plates: true
    expire_after: 10
    // highlight-end
    cameras:
      camera_one:
    labels:
      - license_plate
```

## Retention rules

Retention rules can be used to control the number of snapshots stored on disk.

```yaml /config/config.yaml
storage:
  snapshots:
    tiers:
      - path: / # Files will be stored in the /snapshots/<domain> directory
        max_size:
          gb: 1
```

:::tip

Storage tiers can be used to move snapshots to different storage locations based on age or size.

See the [storage component tiers documentation](/components-explorer/components/storage#tiers) for more information.

:::

:::warning

Size based retention rules are calculated **per camera**, meaning that if you have 2 cameras and set a `max_size` of 1 GB, each camera can store 1 GB of snapshots for a total of 2 GB.

:::

### Setting retention rules per domain

You can set specific retention rules for each domain by following the example below.
The example stores 1 GB of face recognition snapshots, and 7 days if license plate recognition snapshots.

```yaml /config/config.yaml
storage:
  snapshots:
    face_recognition:
      tiers:
        - path: / # Files will be stored in the /snapshots/face_recognition directory
            max_size:
              gb: 1
    license_plate_recognition:
      tiers:
        - path: / # Files will be stored in the /snapshots/license_plate_recognition directory
            max_age:
              days: 7
```

## Downloading snapshots

From the web interface you can download snapshots.

To download a snapshot, you use the `Download Snapshot` button in the event details popup on the `Events` tab. It will download the selected snapshot to a `.jpg` file.

<img
  src="/img/screenshots/Viseron-Events-download-snapshot.png"
  alt-text="Download Snapshot"
  width={700}
/>
