import json
import logging
from queue import Empty, Queue
from threading import Event, Thread
from typing import List

import cv2
from const import LOG_LEVELS
from lib.camera import FFMPEGCamera
from lib.helpers import Filter, draw_objects, draw_zones
from lib.motion import MotionDetection
from lib.mqtt.binary_sensor import MQTTBinarySensor
from lib.recorder import FFMPEGRecorder
from lib.zones import Zone
from lib.detector import DetectedObject

LOGGER = logging.getLogger(__name__)


class MQTT:
    def __init__(self, config, mqtt_queue):
        self._logger = logging.getLogger(__name__ + "." + config.camera.name_slug)
        if getattr(config.camera.logging, "level", None):
            self._logger.setLevel(config.camera.logging.level)

        self.config = config
        self._mqtt_queue = mqtt_queue
        self._zones = []

        self._mqtt_devices = {}
        if self._mqtt_queue:
            self._mqtt_devices["motion_detected"] = MQTTBinarySensor(
                config, mqtt_queue, "motion_detected"
            )
            self._mqtt_devices["object_detected"] = MQTTBinarySensor(
                config, mqtt_queue, "object_detected"
            )
            for label in config.object_detection.labels:
                self._mqtt_devices[label.label] = MQTTBinarySensor(
                    config, mqtt_queue, f"object_detected {label.label}",
                )

    def publish_image(self, frame, zones, resolution):
        if self._mqtt_queue:
            draw_zones(frame.decoded_frame_mat_rgb, zones)
            draw_objects(
                frame.decoded_frame_mat_rgb, frame.objects, resolution,
            )
            # Write a low quality image to save bandwidth
            ret, jpg = cv2.imencode(
                ".jpg", frame.decoded_frame_mat_rgb, [int(cv2.IMWRITE_JPEG_QUALITY), 50]
            )
            if ret:
                self._mqtt_queue.put(
                    {"topic": self.mqtt_camera_state_topic, "payload": jpg.tobytes()}
                )

    def on_connect(self, client):
        # client.publish(
        #     self.mqtt_switch_config_topic,
        #     payload=self.mqtt_switch_config_payload,
        #     retain=True,
        # )

        client.publish(
            self.mqtt_camera_config_topic,
            payload=self.mqtt_camera_config_payload,
            retain=True,
        )

        for device in self._mqtt_devices.values():
            device.on_connect(client)

        for zone in self._zones:
            zone.on_connect(client)

        subscriptions = []
        subscriptions.append(
            {"topic": self.mqtt_switch_command_topic, "callback": self.on_message}
        )
        # self.publish_sensor(False)

        return subscriptions

    def on_message(self, message):
        self._logger.debug(message.payload.decode())
        self._mqtt_queue.put(
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

    # @property
    # def mqtt_sensor_config_payload(self):
    #     payload = {}
    #     payload["name"] = self.config.camera.mqtt_name
    #     payload["state_topic"] = self.mqtt_sensor_state_topic
    #     payload["value_template"] = "{{ value_json.state }}"
    #     payload["availability_topic"] = self.config.mqtt.last_will_topic
    #     payload["payload_available"] = "alive"
    #     payload["payload_not_available"] = "dead"
    #     payload["json_attributes_topic"] = self.mqtt_sensor_state_topic
    #     return json.dumps(payload, indent=3)

    # @property
    # def mqtt_sensor_state_topic(self):
    #     return (
    #         f"{self.config.mqtt.discovery_prefix}/sensor/"
    #         f"{self.config.camera.mqtt_name}/state"
    #     )

    # @property
    # def mqtt_sensor_config_topic(self):
    #     return (
    #         f"{self.config.mqtt.discovery_prefix}/sensor/"
    #         f"{self.config.camera.mqtt_name}/config"
    # )

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
        self._objects_in_fov = []
        self._labels_in_fov = []
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
        for zone in self.config.camera.zones:
            self._zones.append(
                Zone(zone, self.ffmpeg.resolution, self.config, self._mqtt_queue)
            )

        # Motion detector class.
        if self.config.motion_detection.timeout or self.config.motion_detection.trigger:
            self.motion_detector = MotionDetection(self.config, self.motion_event)
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
        self._trigger_recorder = False
        self.recorder_thread = None
        self.recorder = FFMPEGRecorder(self.config, frame_buffer)
        self._logger.debug("NVR thread initialized")

    def event_over(self):
        if self._trigger_recorder or any(zone.trigger_recorder for zone in self._zones):
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
            self.recorder.stop()
            with self.object_return_queue.mutex:  # Clear any objects left in queue
                self.object_return_queue.queue.clear()

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

    def filter_fov(self, objects: List[DetectedObject]):
        objects_in_fov = []
        labels_in_fov = []
        self._trigger_recorder = False
        for obj in objects:
            if self._object_filters.get(obj.label) and self._object_filters[
                obj.label
            ].filter_object(obj):
                obj.relevant = True
                objects_in_fov.append(obj)
                if obj.label not in labels_in_fov:
                    labels_in_fov.append(obj.label)
                if self._object_filters[obj.label].triggers_recording:
                    self._trigger_recorder = True

        self.objects_in_fov = objects_in_fov
        self.labels_in_fov = labels_in_fov

    @property
    def objects_in_fov(self):
        return self._objects_in_fov

    @objects_in_fov.setter
    def objects_in_fov(self, value):
        if value == self._objects_in_fov:
            return

        self._objects_in_fov = value
        if self._mqtt_queue:
            self._mqtt_devices["object_detected"].publish(bool(value))

    @property
    def labels_in_fov(self):
        return self._objects_in_fov

    @labels_in_fov.setter
    def labels_in_fov(self, labels_in_fov):
        if labels_in_fov == self._labels_in_fov:
            return

        labels_added = list(set(labels_in_fov) - set(self._labels_in_fov))
        labels_removed = list(set(self._labels_in_fov) - set(labels_in_fov))

        if self._mqtt_queue:
            for label in labels_added:
                self._mqtt_devices[label].publish(True)
            for label in labels_removed:
                self._mqtt_devices[label].publish(False)

        self._labels_in_fov = labels_in_fov

    def filter_zones(self, objects: List[DetectedObject]):
        for zone in self._zones:
            zone.filter_zone(objects)

    def process_object_event(self, frame):
        if self._trigger_recorder or any(zone.trigger_recorder for zone in self._zones):
            if not self.recorder.is_recording:
                draw_objects(
                    frame.decoded_frame_umat_rgb,
                    self.objects_in_fov,
                    self.ffmpeg.resolution,
                )
                self.start_recording(frame)

    def process_motion_event(self):
        if self.motion_event.is_set():
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

    def run(self):
        """ Main thread. It handles starting/stopping of recordings and
        publishes to MQTT if object is detected. Speed is determined by FPS"""
        self._logger.debug("Waiting for first frame")
        self.frame_ready.wait()
        self._logger.debug("First frame received")

        self.idle_frames = 0
        while not self.kill_received:
            if not self.frame_ready.wait(10):
                self._logger.error("Timeout waiting for frame")
                continue

            # Filter returned objects
            processed_frame = self.get_processed_frame()
            if processed_frame:
                if self._logger.level == LOG_LEVELS["DEBUG"]:
                    self._logger.debug(
                        f"Objects: {[obj.formatted for obj in processed_frame.objects]}"
                    )
                # Filter objects in the FoV
                self.filter_fov(processed_frame.objects)
                # Filter objects in each zone
                self.filter_zones(processed_frame.objects)

            self.process_object_event(processed_frame)
            self.process_motion_event()

            if processed_frame and self.config.camera.publish_image:
                self.publish_image(processed_frame, self._zones, self.ffmpeg.resolution)

            # If we are recording and no object is detected
            if self.recorder.is_recording and self.event_over():
                self.idle_frames += 1
                self.stop_recording()
                continue
            self.idle_frames = 0

        self._logger.info("Exiting NVR thread")

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
