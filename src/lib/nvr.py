import json
import logging
from queue import Empty, Queue
from threading import Event, Thread
from typing import List

import cv2
from lib.camera import FFMPEGCamera
from lib.helpers import draw_objects, draw_zones, Filter
from lib.motion import MotionDetection
from lib.recorder import FFMPEGRecorder
from lib.zones import Zone

LOGGER = logging.getLogger(__name__)


class MQTT:
    def __init__(self, config, mqtt_queue):
        self._logger = logging.getLogger(__name__ + "." + config.camera.name_slug)
        if getattr(config.camera.logging, "level", None):
            self._logger.setLevel(config.camera.logging.level)

        self.config = config
        self.mqtt_queue = mqtt_queue
        self._zones = []

    def publish_sensor(self, object_detected, detections=None):
        if self.mqtt_queue:
            payload = {}
            payload["state"] = "on" if object_detected else "off"
            payload["detections"] = detections
            json_payload = json.dumps(payload, indent=3)

            self.mqtt_queue.put(
                {"topic": self.mqtt_sensor_state_topic, "payload": json_payload}
            )

    def publish_image(self, frame, zones, resolution):
        if self.mqtt_queue:
            draw_zones(frame.decoded_frame_mat_rgb, zones)
            draw_objects(
                frame.decoded_frame_mat_rgb, frame.objects, resolution,
            )
            # Write a low quality image to save bandwidth
            ret, jpg = cv2.imencode(
                ".jpg", frame.decoded_frame_mat_rgb, [int(cv2.IMWRITE_JPEG_QUALITY), 50]
            )
            if ret:
                self.mqtt_queue.put(
                    {"topic": self.mqtt_camera_state_topic, "payload": jpg.tobytes()}
                )

    def on_connect(self, client):
        client.publish(
            self.mqtt_switch_config_topic,
            payload=self.mqtt_switch_config_payload,
            retain=True,
        )

        client.publish(
            self.mqtt_sensor_config_topic,
            payload=self.mqtt_sensor_config_payload,
            retain=True,
        )

        client.publish(
            self.mqtt_camera_config_topic,
            payload=self.mqtt_camera_config_payload,
            retain=True,
        )

        for zone in self._zones:
            zone.on_connect(client)

        subscriptions = []
        subscriptions.append(
            {"topic": self.mqtt_switch_command_topic, "callback": self.on_message}
        )
        self.publish_sensor(False)

        return subscriptions

    def on_message(self, message):
        self._logger.debug(message.payload.decode())
        self.mqtt_queue.put(
            {
                "topic": self.mqtt_switch_state_topic,
                "payload": str(message.payload.decode()),
            }
        )

    @property
    def mqtt_switch_config_payload(self):
        payload = {}
        payload["name"] = self.config.camera.mqtt_name
        payload["command_topic"] = self.mqtt_switch_command_topic
        payload["state_topic"] = self.mqtt_switch_state_topic
        payload["retain"] = True
        payload["availability_topic"] = self.config.mqtt.last_will_topic
        payload["payload_available"] = "alive"
        payload["payload_not_available"] = "dead"
        return json.dumps(payload, indent=3)

    @property
    def mqtt_switch_command_topic(self):
        return (
            f"{self.config.mqtt.discovery_prefix}/switch/"
            f"{self.config.camera.mqtt_name}/set"
        )

    @property
    def mqtt_switch_state_topic(self):
        return (
            f"{self.config.mqtt.discovery_prefix}/switch/"
            f"{self.config.camera.mqtt_name}/state"
        )

    @property
    def mqtt_switch_config_topic(self):
        return (
            f"{self.config.mqtt.discovery_prefix}/switch/"
            f"{self.config.camera.mqtt_name}/config"
        )

    @property
    def mqtt_sensor_config_payload(self):
        payload = {}
        payload["name"] = self.config.camera.mqtt_name
        payload["state_topic"] = self.mqtt_sensor_state_topic
        payload["value_template"] = "{{ value_json.state }}"
        payload["availability_topic"] = self.config.mqtt.last_will_topic
        payload["payload_available"] = "alive"
        payload["payload_not_available"] = "dead"
        payload["json_attributes_topic"] = self.mqtt_sensor_state_topic
        return json.dumps(payload, indent=3)

    @property
    def mqtt_sensor_state_topic(self):
        return (
            f"{self.config.mqtt.discovery_prefix}/sensor/"
            f"{self.config.camera.mqtt_name}/state"
        )

    @property
    def mqtt_sensor_config_topic(self):
        return (
            f"{self.config.mqtt.discovery_prefix}/sensor/"
            f"{self.config.camera.mqtt_name}/config"
        )

    @property
    def mqtt_camera_config_payload(self):
        payload = {}
        payload["name"] = self.config.camera.mqtt_name
        payload["topic"] = self.mqtt_camera_state_topic
        payload["availability_topic"] = self.config.mqtt.last_will_topic
        payload["payload_available"] = "alive"
        payload["payload_not_available"] = "dead"
        return json.dumps(payload, indent=3)

    @property
    def mqtt_camera_state_topic(self):
        return (
            f"{self.config.mqtt.discovery_prefix}/camera/"
            f"{self.config.camera.mqtt_name}/image"
        )

    @property
    def mqtt_camera_config_topic(self):
        return (
            f"{self.config.mqtt.discovery_prefix}/camera/"
            f"{self.config.camera.mqtt_name}/config"
        )


class FFMPEGNVR(Thread, MQTT):
    nvr_list: List[object] = []

    def __init__(self, config, detector, detector_queue, mqtt_queue=None):
        Thread.__init__(self)
        MQTT.__init__(self, config, mqtt_queue)
        self.nvr_list.append({config.camera.mqtt_name: self})
        self._logger.debug("Initializing NVR thread")

        self.config = config
        self.kill_received = False

        self.frame_ready = Event()
        self.object_in_view = False
        self.scan_for_objects = Event()  # Set when frame should be scanned
        self.motion_event = Event()  # Triggered when motion detected
        self.scan_for_motion = Event()  # Set when frame should be scanned
        self.idle_frames = 0

        if self.config.motion_detection.trigger:
            self.scan_for_motion.set()
            self.scan_for_objects.clear()
        else:
            self.scan_for_objects.set()
            self.scan_for_motion.clear()

        object_decoder_queue = Queue(maxsize=2)
        motion_decoder_queue = Queue(maxsize=2)
        motion_queue = Queue(maxsize=2)
        self.object_return_queue = Queue(maxsize=20)

        # Use FFMPEG to read from camera. Used for reading/recording
        # Maxsize changes later based on config option LOOKBACK_SECONDS
        frame_buffer = Queue(maxsize=1)
        self.ffmpeg = FFMPEGCamera(self.config, frame_buffer)

        self._object_filters = {}
        for object_filter in self.config.object_detection.labels:
            self._object_filters[object_filter.label] = Filter(object_filter)

        self._zones = []
        self._logger.debug(self.config)
        for zone in self.config.camera.zones:
            self._zones.append(
                Zone(zone, self.ffmpeg.resolution, self.config, self.mqtt_queue)
            )

        # Motion detector class.
        if self.config.motion_detection.timeout or self.config.motion_detection.trigger:
            self.motion_detector = MotionDetection(
                self.motion_event,
                self.config.motion_detection.area,
                self.config.motion_detection.frames,
            )
            self.motion_thread = Thread(
                target=self.motion_detector.motion_detection, args=(motion_queue,)
            )
            self.motion_thread.daemon = True
            self.motion_thread.start()

            self.motion_decoder = Thread(
                target=self.ffmpeg.decoder,
                args=(
                    motion_decoder_queue,
                    motion_queue,
                    self.config.motion_detection.width,
                    self.config.motion_detection.height,
                ),
            )
            self.motion_decoder.daemon = True
            self.motion_decoder.start()

        # Start a process to pipe ffmpeg output
        self.ffmpeg_grabber = Thread(
            target=self.ffmpeg.capture_pipe,
            args=(
                frame_buffer,
                self.frame_ready,
                self.config.object_detection.interval,
                object_decoder_queue,
                self.scan_for_objects,
                self.object_return_queue,
                self.config.motion_detection.interval,
                motion_decoder_queue,
                self.scan_for_motion,
            ),
        )
        self.ffmpeg_grabber.daemon = True

        self.ffmpeg_decoder = Thread(
            target=self.ffmpeg.decoder,
            args=(
                object_decoder_queue,
                detector_queue,
                detector.model_width,
                detector.model_height,
            ),
        )
        self.ffmpeg_decoder.daemon = True

        self.ffmpeg_grabber.start()
        self.ffmpeg_decoder.start()

        # Initialize recorder
        self.recorder_thread = None
        self.recorder = FFMPEGRecorder(self.config, frame_buffer)
        self._logger.debug("NVR thread initialized")

    def event_over(self):
        if self.object_in_view:
            return False
        if self.config.motion_detection.timeout and self.motion_event.is_set():
            return False
        return True

    def start_recording(self, thumbnail):
        self.recorder_thread = Thread(
            target=self.recorder.start_recording,
            args=(
                thumbnail,
                self.ffmpeg.stream_width,
                self.ffmpeg.stream_height,
                self.ffmpeg.stream_fps,
            ),
        )
        self.recorder_thread.start()
        if self.config.motion_detection.timeout and not self.scan_for_motion.is_set():
            self.scan_for_motion.set()
            self._logger.info("Starting motion detector")

    def stop_recording(self):
        if self.idle_frames % self.ffmpeg.stream_fps == 0:
            self._logger.info(
                "Stopping recording in: {}".format(
                    int(
                        self.config.recorder.timeout
                        - (self.idle_frames / self.ffmpeg.stream_fps)
                    )
                )
            )

        if self.idle_frames >= (self.ffmpeg.stream_fps * self.config.recorder.timeout):
            self.publish_sensor(False)
            self.recorder.stop()

            if self.config.motion_detection.trigger:
                self.scan_for_objects.clear()
                self._logger.info("Pausing object detector")
            else:
                self.scan_for_motion.clear()
                self._logger.info("Pausing motion detector")

    def get_processed_frame(self):
        """ Returns a frame along with its detections which has been processed
        by the object detector """
        try:
            return self.object_return_queue.get_nowait()["frame"]
        except Empty:
            return None

    def filter_objects(self, objects):
        filtered_objects = []
        for obj in objects:
            if self._object_filters.get(obj["label"]) and self._object_filters[
                obj["label"]
            ].filter_object(obj):
                filtered_objects.append(obj)
        return filtered_objects

    def filter_zones(self, objects):
        for zone in self._zones:
            zone.filter_zone(objects)

    def motion(self):
        if self.motion_event.is_set():
            self.idle_frames = 0
            if (
                self.config.motion_detection.trigger
                and not self.scan_for_objects.is_set()
            ):
                self.scan_for_objects.set()
                self._logger.debug("Motion detected! Starting object detector")
        elif (
            self.scan_for_objects.is_set()
            and not self.recorder.is_recording
            and self.config.motion_detection.trigger
        ):
            self._logger.debug("Not recording, pausing object detector")
            self.scan_for_objects.clear()

    def object_detection(self, frame, filtered_objects):
        if self.object_in_view:
            self.idle_frames = 0
            if not self.recorder.is_recording:
                thumbnail = draw_objects(
                    frame.decoded_frame_umat_rgb,
                    filtered_objects,
                    self.ffmpeg.resolution,
                )
                self.start_recording(thumbnail)

    def run(self):
        """ Main thread. It handles starting/stopping of recordings and
        publishes to MQTT if object is detected. Speed is determined by FPS"""
        self._logger.debug("Waiting for first frame")
        self.frame_ready.wait()
        self._logger.debug("First frame received")

        self.idle_frames = 0
        while not self.kill_received:
            filtered_objects = []
            if not self.frame_ready.wait(10):
                self._logger.error("Timeout waiting for frame")
                continue

            # Filter returned objects
            processed_frame = self.get_processed_frame()
            if processed_frame:
                self._logger.debug(f"Objects: {processed_frame.objects}")
                filtered_objects = self.filter_objects(processed_frame.objects)

            # Check if any filtered object is in the FoV
            if filtered_objects:
                if not self.object_in_view:
                    self.object_in_view = True
            elif self.object_in_view:
                self.object_in_view = False

            # Check if any filtered object is in a particular zone
            if filtered_objects:
                self.filter_zones(processed_frame.objects)

            self.object_detection(processed_frame, filtered_objects)
            self.motion()

            if processed_frame:
                self.publish_image(processed_frame, self._zones, self.ffmpeg.resolution)

            # If we are recording and no object is detected
            if self.recorder.is_recording and self.event_over():
                self.idle_frames += 1
                self.stop_recording()

        self._logger.info("Exiting NVR thread")

    @property
    def object_in_view(self):
        return self._object_in_view

    @object_in_view.setter
    def object_in_view(self, value):
        self.publish_sensor(value, [])
        self._object_in_view = value
        return self._object_in_view

    def stop(self):
        self._logger.info("Stopping NVR thread")
        self.kill_received = True

        # Stop potential recording
        if self.recorder.is_recording:
            self.recorder.stop()
            self.recorder_thread.join()

        # Stop frame grabber
        self.ffmpeg.release()
        self.ffmpeg_grabber.join()
