Ideas
- Config object
  Create a proper config object from a yaml file
  Validate using voluptuous

- Watchdog
  Build a watchdog for the camera process

- Weaving
  If detection is triggered close to previous detection, send silent alarm and "weave" the videos together.

- Dynamic detection interval:
  Speed up interval when detection happens for all types of detectors

- Properties:
  All public vars should be exposed by property

- Decouple MQTT
  - One client object.
  - Start all camera threads, which need to expose an on_message function
  - Pass list of camera objects to MQTT
