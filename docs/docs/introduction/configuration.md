# Configuration

Viseron uses a YAML based configuration.

If no `/config/config.yaml` is found, a default one will be created for you.<br />
You need to fill this in order for Viseron to function. <br />

You can edit the `config.yaml` in whatever way you like, but using the built in Configuration Editor is recommended.

:::tip

The built in Configuration Editor has syntax highlighting, making your YAML endevours a bit easier.

:::

## Components

Viserons config consists of [components](/docs/components).<br />
Every component provides different sets of domains (such as cameras, object detection, motion detection etc).<br />
These domains are then tied together, providing the full capabilities of Viseron.

Components generally implement at least one domain.<br />
:::info

You can mix and match components freely. For example you could use different object detectors for different cameras.

:::

## Domains

Below is a short description of each domain and its general capabilities.

### Camera domain

The `camera` domain is the base of it all.
This is the domain that connects to your camera and fetches frames for processing.
Each camera has a unique `camera identifier` which flows through the entire configuration.

### Object Detector domain

The object detector domain scans for objects at requested intervals, sending events on detections for other parts of Viseron to consume.<br />
:::info

Object detection can be configured to run all the time so you never miss anything, or only when there is detected motion, saving some resources.<br/>
Whatever floats your boat!
:::

### Motion Detector domain

The motion detector domain works in a similar way to the object detector.
When motion is detected, an event will be emitted and it will, if configured, start the object detector.

:::info

The motion detector can be configured to start recordings as well, bypassing the need for an object detector.

:::

### NVR domain

The NVR domain is what glues all the other domains together.
It handles:

- Fetches frames from the cameras
- Sends them to the detectors
- Starts and stops the recorder
- Sends frames to [post processors](#post-processors)

### Post Processors

TODO

### Face Recognition

TODO

### Image Classification

TODO

## Secrets

Any value in `config.yaml` can be substituted with secrets stored in `secrets.yaml`.<br />
This can be used to remove any private information from your `config.yaml` to make it easier to share your `config.yaml` with others.

Here is a simple usage example.<br />

```yaml title="/config/secrets.yaml"
camera_ip: 192.168.1.2
username: coolusername
password: supersecretpassword
```

```yaml title="/config/config.yaml"
cameras:
  - name: Front Door
    host: !secret camera_ip
    username: !secret username
    password: !secret password
```

:::info

The `secrets.yaml` is expected to be in the same folder as `config.yaml`.<br />
The full path needs to be `/config/secrets.yaml`.

:::
