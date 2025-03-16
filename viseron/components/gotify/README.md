# Gotify Component for Viseron

This component allows Viseron to send notifications to a [Gotify](https://gotify.net/) server when recordings start.

## What is Gotify?

Gotify is a simple server for sending and receiving push notifications. It's self-hosted, open-source, and provides a simple way to send notifications to your devices.

## Installation

1. Set up a Gotify server if you don't already have one. You can follow the [official documentation](https://gotify.net/docs/install).
2. Create an application in Gotify and get the application token.
3. Configure the Gotify component in your Viseron configuration file.

## Configuration

Add the following to your Viseron configuration file:

```yaml
gotify:
  gotify_url: "https://gotify.example.com"  # URL to your Gotify server
  gotify_token: "YOUR_APPLICATION_TOKEN"     # Application token from Gotify
  priority: 5                               # Priority of the notifications (1-10)
  detection_label: "person,cat"             # Labels of objects to send notifications for
  send_thumbnail: false                     # Send a thumbnail of the detected object
  cameras:
    camera1:                              # Camera identifier with empty config
    camera2:                              # Another camera identifier
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `gotify_url` | URL to your Gotify server (required) | - |
| `gotify_token` | Application token from Gotify (required) | - |
| `priority` | Priority of the notifications (1-10) | 5 |
| `detection_label` | Label(s) of the object(s) to send notifications for (comma-separated for multiple labels, e.g., "person,cat") | "person" |
| `send_thumbnail` | Send a thumbnail of the detected object | false |
| `cameras` | List of cameras to get notifications from (required) | - |

### Camera-specific Configuration Options

Each camera can have its own configuration options:

| Option | Description | Default |
|--------|-------------|---------|
| `detection_label` | Label(s) of the object(s) to send notifications for this camera (comma-separated for multiple labels, e.g., "person,cat") | Global setting |
| `send_thumbnail` | Send a thumbnail of the detected object for this camera | Global setting |

## Features

- Send notifications to Gotify when recordings start
- Include thumbnails of detected objects in notifications (when enabled)
- Configure notification priority
- Filter notifications by object type
- Only send notifications for objects that trigger recordings

## How It Works

The Gotify component listens for the `EVENT_RECORDER_START` event, which is triggered when a recording starts. When this event occurs, the component:

1. Checks if the recording contains objects
2. Filters objects based on the configured detection labels
3. Sends a notification to the Gotify server with:
   - A text message
   - A thumbnail image (if `send_thumbnail` is enabled and a thumbnail is available)

This ensures that notifications are only sent when recordings are actually triggered, reducing unnecessary notifications.

## Limitations

- Gotify doesn't support direct video uploads, so the component only sends a notification that a video was recorded
- Image thumbnails are sent as base64-encoded images in markdown format, which requires a Gotify client that supports this format

## Troubleshooting

- Ensure your Gotify server is accessible from the device running Viseron
- Check that the application token has the correct permissions
- Verify that the URL is correct and includes the protocol (http:// or https://)
- Look for error messages in the Viseron logs
