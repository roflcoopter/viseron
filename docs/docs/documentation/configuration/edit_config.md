# Edit configuration

To edit or change your `config.yaml`, you can either access the file directly on your system, use the built in `Configuration Editor` in the Viseron frontend, or use the `Camera Tuning` page to edit specific camera settings.

## Configuration Editor

The `Configuration Editor` is a convenient way to make changes to your configuration without having to access the file system.

:::tip

The built in Configuration Editor has syntax highlighting, making your YAML endeavors a bit easier.

<details>
  <summary>Demonstration of the Editor</summary>

<p align="center">
  <img src="/img/screenshots/Viseron-demo-configuration.gif" alt-text="Configuration Editor"/>
</p>

</details>

:::

## Camera Tuning

The `Camera Tuning` page allows you to edit specific settings for each camera, drawing masks, and more. This is a great way to quickly adjust camera settings without having to navigate through the entire configuration file.

:::warning

This is an experimental feature and is not fully fleshed out yet. Not all settings are available to edit here, but the long-term goal is to have all camera settings available for easy tuning.

:::

You access tuning by clicking on the `Camera Tuning` button on a camera card on the main page.

<details>
  <summary>Camera Tuning button (highlighted in green)</summary>
  <img src="/img/ui/tune/camera-tuning-button.png" alt-text="Camera Tuning button" />
</details>

<img
src="/img/ui/tune/main.png"
alt-text="Camera Tuning page"
width={700}
/>

:::note

Note that you still need to restart Viseron after changing the settings for the changes to take effect.
A future release will include hot reloading of all settings to make this process more seamless.
Most code is already in place for this but it has not been exposed to the frontend properly yet.

:::
