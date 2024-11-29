# Secrets

Any value in `config.yaml` can be substituted with secrets stored in `secrets.yaml`.<br />
This can be used to remove any private information from your `config.yaml` to make it easier to share your `config.yaml` with others.

Here is a simple usage example:

```yaml title="/config/secrets.yaml"
camera_one_host: 192.168.1.2
camera_one_username: coolusername
camera_one_password: supersecretpassword

camera_two_host: 192.168.1.3
camera_two_username: anotherusername
camera_two_password: moresecretpassword
```

```yaml title="/config/config.yaml"
ffmpeg:
  camera:
    camera_one:
      name: Camera 1
      host: !secret camera_one_host
      path: /Streaming/Channels/101/
      username: !secret camera_one_username
      password: !secret camera_one_password
    camera_two:
      name: Camera 2
      host: !secret camera_two_host
      path: /Streaming/Channels/101/
      username: !secret camera_two_username
      password: !secret camera_two_password
```

:::info

The `secrets.yaml` is expected to be in the same folder as `config.yaml`.<br />
The full path needs to be `/config/secrets.yaml`.

:::
