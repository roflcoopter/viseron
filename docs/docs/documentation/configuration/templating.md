# Templating

Templating in Viseron is backed by [Jinja2](https://jinja.palletsprojects.com/), a powerful templating engine for Python.
It allows you to create dynamic templates that can be used in the config, currently only the [webhook component](/components-explorer/components/webhook) leverages this functionality.

## Templating in Viseron

To know if a config option supports templating, check for the `Jinja2 template` tag in the component documentation.

<details>
  <summary>Jinja2 template tag screenshot</summary>
  <img
    src="/img/screenshots/Viseron-Docs-jinja-template.png"
    alt-text="Jinja2 Template"
    width={700}
  />
</details>

The syntax for Jinja2 is described in [their documentation](https://jinja.palletsprojects.com/en/latest/templates/) and is not covered here.

Viseron provides some additional context variables that can be used in templates:

- `states`: A dictionary of all the current states of all Entities in Viseron.
- `event`: The event data that triggered the component. This is only available for components that are triggered by events, such as the [webhook component](/components-explorer/components/webhook).

## Examples

### Using the `event` context variable

When using the `webhook` component, you can access the event data that triggered the webhook. For example, if you want to include the camera identifier in the payload, you can use:

```yaml
webhook:
  my_webhook:
    trigger:
      event: camera_one/motion_detected
    url: http://example.com/webhook
    payload: >
      {%- if event.motion_detected -%}
          "Motion detected on {{ event.camera_identifier }}!"
      {%- else -%}
          "No motion detected on {{ event.camera_identifier }}."
      {%-  endif -%}
```

### Using the `states` context variable

You can also use the `states` context variable to access the current state of all Entities. For example, if you want to include a camera's recording state in the payload, you can use:

```yaml
webhook:
  my_webhook:
    trigger:
      event: camera_one/motion_detected
    url: http://example.com/webhook
    payload: "Recording state: {{ states.camera_one_recorder.state }}"
```

### Conditions

Some components allow you to use template conditions to determine whether an action should be taken based on the template.
The condition checks whether the template produces a value that evaluates to true.

Values that evaluate to true include:

- Boolean true
- Non zero numbers (e.g., 1, 2, 3, etc.)
- The strings `true`, `yes`, `on`, `enable` (case-insensitive)

Any other value results in a false evaluation.

This example checks if the `motion_detected` attribute of the event is true before triggering the webhook:

```yaml
webhook:
  my_webhook:
    trigger:
      event: camera_one/motion_detected
      condition: >
        {{ event.motion_detected }}
    url: http://example.com/webhook
    payload: "Motion detected on {{ event.camera_identifier }}"
```
