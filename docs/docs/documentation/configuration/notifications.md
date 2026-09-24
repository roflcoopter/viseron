# Pausing notifications

Notifications can be paused for a single camera or for all cameras. This covers the [Discord](/components-explorer/components/discord), [Gotify](/components-explorer/components/gotify), [Telegram](/components-explorer/components/telegram) and [Webhook](/components-explorer/components/webhook) components.

A pause either ends after a set duration or lasts until it is resumed. Pauses are kept in memory, so restarting Viseron resumes all notifications.

Pausing requires the `admin` or `write` role.

## Web interface

On the `Cameras` page, click the bell on a camera card to pause that camera for 15 minutes, 1 hour, 4 hours, 8 hours, or until resumed. While a camera is paused, its bell is crossed out and its tooltip shows when notifications resume. Click the bell again to resume early.

To pause all cameras at once, use `Pause notifications` above the camera cards.

## REST API

To pause a single camera, send a `POST` request to the `/api/v1/camera/<camera identifier>/notifications` endpoint with the following JSON payload:

```json
{
  "action": "pause",
  "duration": 3600 // Optional, duration in seconds. Leave out to pause until resumed
}
```

To resume it, send a `POST` request to the same endpoint with the JSON payload:

```json
{
  "action": "resume"
}
```

To pause or resume all cameras, send the same payloads to the `/api/v1/cameras/notifications` endpoint.

The current pause is included in the camera response from `/api/v1/camera/<camera identifier>` as `notifications_paused` and `notifications_paused_until`. It is also exposed as the `sensor.<camera identifier>_notifications_paused_until` entity.

## Webhooks

A webhook is paused when its triggering event belongs to a paused camera. Webhooks triggered by events that are not tied to a camera always run.
