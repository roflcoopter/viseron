# System Events

System events are events that are dispatched by the backend for communication between the many components of Viseron, such as when a camera detects motion or an object is detected.

These events can be used to trigger actions in other components, such as the [webhook component](/components-explorer/components/webhook).

## System event viewer

The system event viewer allows you to listen to and view system events in real-time, along with the event data. Seeing the event data can be useful for when you want to use the event data in a [template](/docs/documentation/configuration/templating).

The event viewer can be accessed by admins from the Settings > System Events page in the Viseron web interface.

<img
  src="/img/screenshots/Viseron-Settings-system-event-viewer.png"
  alt-text="System Event Viewer"
  width={700}
/>

:::info

The event data is normally in JSON format, but the event viewer will format it to YAML for easier readability.

:::

## Common events

Viseron has many system events. The events below are the ones most commonly used in webhooks and templates. Replace `camera_identifier`, `zone_name`, and `face` with the values from your configuration, for example `camera_one/objects`.

Use the System Event Viewer to inspect the exact data for your installation. In [templates](/docs/documentation/configuration/templating), the event data is available as `event`.

### Accessing event data in templates

Object events expose `objects` as a list. Access one object by index or loop over the list:

```yaml
payload: "Detected {{ event.objects[0].label }} on {{ event.camera_identifier }}"
```

Check that the list contains objects before indexing it:

```yaml
payload: >
  {% if event.objects %}
    Detected {{ event.objects[0].label }}
  {% else %}
    No objects detected
  {% endif %}
```

To include every detected object:

```yaml
payload: >
  {% for object in event.objects %}
    {{ object.label }} {{ object.confidence }}
  {% endfor %}
```

### Object detection

| Event | Payload fields |
| --- | --- |
| `{camera_identifier}/objects` | `camera_identifier`, `objects`, `zone` |
| `{camera_identifier}/zone/{zone_name}/objects` | `camera_identifier`, `objects`, `zone` |

`objects` is a list. Each object contains:

- `label`
- `confidence`
- `rel_width`
- `rel_height`
- `rel_x1`
- `rel_y1`
- `rel_x2`
- `rel_y2`

`zone` is `null` for `{camera_identifier}/objects`. For `{camera_identifier}/zone/{zone_name}/objects`, `zone` contains the zone data, including `name`, `camera_identifier`, and `coordinates`.

Example:

```json
{
  "camera_identifier": "camera_one",
  "objects": [
    {
      "label": "person",
      "confidence": 0.91,
      "rel_width": 0.2,
      "rel_height": 0.5,
      "rel_x1": 0.1,
      "rel_y1": 0.2,
      "rel_x2": 0.3,
      "rel_y2": 0.7
    }
  ],
  "zone": null
}
```

### Motion detection

| Event | Payload fields |
| --- | --- |
| `{camera_identifier}/motion_detected` | `camera_identifier`, `motion_detected`, `max_area` |

`motion_detected` is `true` when motion starts and `false` when motion stops. `max_area` is the largest detected motion contour area, or `null` when no contour data is attached.

Example:

```json
{
  "camera_identifier": "camera_one",
  "motion_detected": true,
  "max_area": 0.12
}
```

### Recorder

| Event | Payload fields |
| --- | --- |
| `{camera_identifier}/recorder/start` | `camera`, `recording` |
| `{camera_identifier}/recorder/stop` | `camera`, `recording` |

`camera` contains the camera data, including `identifier` and `name`.

`recording` contains:

- `id`
- `start_time`
- `start_timestamp`
- `end_time`
- `end_timestamp`
- `date`
- `thumbnail_path`
- `objects`
- `trigger_type`

`end_time` and `end_timestamp` are `null` when the recorder starts and populated when it stops. `recording.objects` is a list of detected objects with the same fields as object detection events.

Example template:

```yaml
payload: "Recording {{ event.recording.id }} started on {{ event.camera.identifier }}"
```

### Face recognition

| Event | Payload fields |
| --- | --- |
| `{camera_identifier}/face/detected/{face}` | `camera_identifier`, `face` |

`face` contains:

- `name`
- `coordinates`
- `confidence`
- `extra_attributes`

Example template:

```yaml
payload: "Detected {{ event.face.name }} with confidence {{ event.face.confidence }}"
```
