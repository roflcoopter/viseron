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
