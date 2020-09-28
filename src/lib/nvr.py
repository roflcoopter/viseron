import logging
from queue import Empty, Queue
from threading import Thread
from typing import List

import cv2

from const import LOG_LEVELS
from lib.camera import FFMPEGCamera
from lib.helpers import Filter, draw_contours, draw_mask, draw_objects, draw_zones
from lib.motion import MotionDetection
from lib.mqtt.binary_sensor import MQTTBinarySensor
from lib.mqtt.camera import MQTTCamera
from lib.mqtt.switch import MQTTSwitch
from lib.recorder import FFMPEGRecorder
from lib.zones import Zone

LOGGER = logging.getLogger(__name__)


class MQTT:
    def __init__(self, config, mqtt_queue):
        self.config = config
        self.mqtt_queue = mqtt_queue

        self.devices = {}
        if self.mqtt_queue:
            self.devices["motion_detected"] = MQTTBinarySensor(
                config, mqtt_queue, "motion_detected"
            )
            self.devices["object_detected"] = MQTTBinarySensor(
                config, mqtt_queue, "object_detected"
            )
            for label in config.object_detection.labels:
                self.devices[label.label] = MQTTBinarySensor(
                    config, mqtt_queue, f"object_detected {label.label}",
                )
            self.devices["switch"] = MQTTSwitch(config, mqtt_queue)
            self.devices["camera"] = MQTTCamera(config, mqtt_queue)

    def publish_image(self, object_frame, motion_frame, zones, resolution):
        if self.mqtt_queue:
            # Draw on the object frame if it is supplied
            frame = object_frame if object_frame else motion_frame
            if self.config.motion_detection.mask:
                draw_mask(
                    frame.decoded_frame_mat_rgb, self.config.motion_detection.mask,
                )

            if motion_frame and frame.motion_contours:
                draw_contours(
                    frame.decoded_frame_mat_rgb,
                    frame.motion_contours,
                    resolution,
                    self.config.motion_detection.area,
                )

            draw_zones(frame.decoded_frame_mat_rgb, zones)
            draw_objects(
                frame.decoded_frame_mat_rgb, frame.objects, resolution,
            )

            # Write a low quality image to save bandwidth
            ret, jpg = cv2.imencode(
                ".jpg", frame.decoded_frame_mat_rgb, [int(cv2.IMWRITE_JPEG_QUALITY), 50]
            )
            if ret:
                self.devices["camera"].publish(jpg.tobytes())

    def on_connect(self, client):
        subscriptions = {}

        for device in self.devices.values():
            device.on_connect(client)
            if getattr(device, "on_message", False):
                subscriptions[device.command_topic] = [device.on_message]

        return subscriptions

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


class FFMPEGNVR(Thread):
    nvr_list: List[object] = []

    def __init__(
        self, config, detector, detector_queue, post_processors, mqtt_queue=None
    ):
        Thread.__init__(self)
        self.nvr_list.append({config.camera.mqtt_name: self})
        self.setup_loggers(config)
        self._logger.debug("Initializing NVR thread")

        self._mqtt = MQTT(config, mqtt_queue)
        self.config = config
        self.kill_received = False
        self.camera_grabber = None

        self._objects_in_fov = []
        self._labels_in_fov = []
        self.idle_frames = 0
        self._motion_frames = 0
        self._motion_detected = False
        self._motion_only_frames = 0
        self._motion_max_timeout_reached = False

        self.detector = detector

        self._post_processors = post_processors

        self._object_decoder_queue = Queue(maxsize=2)
        self._motion_decoder_queue = Queue(maxsize=2)
        motion_queue = Queue(maxsize=2)
        self.object_return_queue = Queue(maxsize=20)
        self.motion_return_queue = Queue(maxsize=20)

        # Use FFMPEG to read from camera. Used for reading/recording
        # Maxsize changes later based on config option LOOKBACK_SECONDS
        frame_buffer = Queue(maxsize=1)
        self.camera = FFMPEGCamera(config, frame_buffer)

        if config.motion_detection.trigger_detector:
            self.camera.scan_for_motion.set()
            self.camera.scan_for_objects.clear()
        else:
            self.camera.scan_for_objects.set()
            self.camera.scan_for_motion.clear()

        self._object_filters = {}
        for object_filter in config.object_detection.labels:
            self._object_filters[object_filter.label] = Filter(object_filter)

        self._zones = []
        for zone in config.camera.zones:
            self._zones.append(
                Zone(
                    zone,
                    self.camera.resolution,
                    config,
                    self._mqtt.mqtt_queue,
                    post_processors,
                )
            )

        # Motion detector class.
        if config.motion_detection.timeout or config.motion_detection.trigger_detector:
            self.motion_detector = MotionDetection(config, self.camera.resolution)
            self.motion_thread = Thread(
                target=self.motion_detector.motion_detection, args=(motion_queue,)
            )
            self.motion_thread.daemon = True
            self.motion_thread.start()

            self.motion_decoder = Thread(
                target=self.camera.decoder,
                args=(
                    self._motion_decoder_queue,
                    motion_queue,
                    config.motion_detection.width,
                    config.motion_detection.height,
                ),
            )
            self.motion_decoder.daemon = True
            self.motion_decoder.start()

        self.camera_decoder = Thread(
            target=self.camera.decoder,
            args=(
                self._object_decoder_queue,
                detector_queue,
                detector.model_width,
                detector.model_height,
            ),
        )
        self.camera_decoder.daemon = True
        self.camera_decoder.start()

        self.start_camera()

        # Initialize recorder
        self._trigger_recorder = False
        self.recorder_thread = None
        self.recorder = FFMPEGRecorder(config, frame_buffer)

        self._logger.debug("NVR thread initialized")

    def setup_loggers(self, config):
        self._logger = logging.getLogger(__name__ + "." + config.camera.name_slug)
        if getattr(config.camera.logging, "level", None):
            self._logger.setLevel(config.camera.logging.level)

        self._motion_logger = logging.getLogger(
            __name__ + "." + config.camera.name_slug + ".motion"
        )

        if getattr(config.motion_detection.logging, "level", None):
            self._motion_logger.setLevel(config.motion_detection.logging.level)
        elif getattr(config.camera.logging, "level", None):
            self._motion_logger.setLevel(config.camera.logging.level)

        self._object_logger = logging.getLogger(
            __name__ + "." + config.camera.name_slug + ".object"
        )

        if getattr(config.object_detection.logging, "level", None):
            self._object_logger.setLevel(config.object_detection.logging.level)
        elif getattr(config.camera.logging, "level", None):
            self._object_logger.setLevel(config.camera.logging.level)

    def on_connect(self, client):
        """Called when MQTT connection is established"""
        subscriptions = self._mqtt.on_connect(client)

        for zone in self._zones:
            zone.on_connect(client)

        # We subscribe to the switch topic to toggle camera on/off
        subscriptions[self._mqtt.devices["switch"].command_topic].append(
            self.toggle_camera
        )

        return subscriptions

    def toggle_camera(self, message):
        self._logger.debug(f"TOGGLING camera {message.payload.decode()}")
        if message.payload.decode() == "ON":
            self.start_camera()
            return
        if message.payload.decode() == "OFF":
            self.stop_camera()
            return

    def start_camera(self):
        if not self.camera_grabber or not self.camera_grabber.is_alive():
            self._logger.debug("Starting camera")
            self.camera_grabber = Thread(
                target=self.camera.capture_pipe,
                args=(
                    self.config.object_detection.interval,
                    self._object_decoder_queue,
                    self.object_return_queue,
                    self.config.motion_detection.interval,
                    self._motion_decoder_queue,
                    self.motion_return_queue,
                ),
            )
            self.camera_grabber.daemon = True
            self.camera_grabber.start()

    def stop_camera(self):
        self._logger.debug("Stopping camera")
        self.camera.release()

    def event_over(self):
        if self._trigger_recorder or any(zone.trigger_recorder for zone in self._zones):
            self._motion_max_timeout_reached = False
            self._motion_only_frames = 0
            return False
        if self.config.motion_detection.timeout and self.motion_detected:
            # Only allow motion to keep event active for a specified period of time
            if self._motion_only_frames >= (
                self.camera.stream_fps * self.config.motion_detection.max_timeout
            ):
                if not self._motion_max_timeout_reached:
                    self._motion_max_timeout_reached = True
                    self._logger.debug(
                        "Motion has stalled recorder for longer than max_timeout, "
                        "event considered over anyway"
                    )
                return True
            self._motion_only_frames += 1
            return False
        return True

    def start_recording(self, thumbnail):
        self.recorder_thread = Thread(
            target=self.recorder.start_recording,
            args=(
                thumbnail,
                self.camera.stream_width,
                self.camera.stream_height,
                self.camera.stream_fps,
            ),
        )
        self.recorder_thread.start()
        if (
            self.config.motion_detection.timeout
            and not self.camera.scan_for_motion.is_set()
        ):
            self.camera.scan_for_motion.set()
            self._logger.info("Starting motion detector")

    def stop_recording(self):
        if self.idle_frames % self.camera.stream_fps == 0:
            self._logger.info(
                "Stopping recording in: {}".format(
                    int(
                        self.config.recorder.timeout
                        - (self.idle_frames / self.camera.stream_fps)
                    )
                )
            )

        if self.idle_frames >= (self.camera.stream_fps * self.config.recorder.timeout):
            self.recorder.stop()
            with self.object_return_queue.mutex:  # Clear any objects left in queue
                self.object_return_queue.queue.clear()

            if self.config.motion_detection.trigger_detector:
                self.camera.scan_for_objects.clear()
                self._logger.info("Pausing object detector")
            else:
                self.camera.scan_for_motion.clear()
                self._logger.info("Pausing motion detector")

    def get_processed_object_frame(self):
        """ Returns a frame along with its detections which has been processed
        by the object detector """
        try:
            return self.object_return_queue.get_nowait()["frame"]
        except Empty:
            return None

    def filter_fov(self, frame):
        objects_in_fov = []
        labels_in_fov = []
        self._trigger_recorder = False
        for obj in frame.objects:
            if self._object_filters.get(obj.label) and self._object_filters[
                obj.label
            ].filter_object(obj):
                obj.relevant = True
                objects_in_fov.append(obj)
                if obj.label not in labels_in_fov:
                    labels_in_fov.append(obj.label)

                if self._object_filters[obj.label].triggers_recording:
                    self._trigger_recorder = True

                # Send detection to configured post processors
                if self._object_filters[obj.label].post_processor:
                    self._post_processors[
                        self._object_filters[obj.label].post_processor
                    ].input_queue.put({"frame": frame, "object": obj})

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
        if self._mqtt.mqtt_queue:
            self._mqtt.devices["object_detected"].publish(bool(value))

    @property
    def labels_in_fov(self):
        return self._objects_in_fov

    @labels_in_fov.setter
    def labels_in_fov(self, labels_in_fov):
        if labels_in_fov == self._labels_in_fov:
            return

        labels_added = list(set(labels_in_fov) - set(self._labels_in_fov))
        labels_removed = list(set(self._labels_in_fov) - set(labels_in_fov))

        if self._mqtt.mqtt_queue:
            for label in labels_added:
                self._mqtt.devices[label].publish(True)
            for label in labels_removed:
                self._mqtt.devices[label].publish(False)

        self._labels_in_fov = labels_in_fov

    def filter_zones(self, frame):
        for zone in self._zones:
            zone.filter_zone(frame)

    def get_processed_motion_frame(self):
        """ Returns a frame along with its motion contours which has been processed
        by the motion detector """
        try:
            return self.motion_return_queue.get_nowait()["frame"]
        except Empty:
            return None

    def filter_motion(self, motion_contours):
        _motion_found = bool(
            motion_contours.max_area > self.config.motion_detection.area
        )

        if _motion_found:
            self._motion_frames += 1
            self._motion_logger.debug(
                "Consecutive frames with motion: {}, "
                "max area size: {}".format(
                    self._motion_frames, motion_contours.max_area
                )
            )

            if self._motion_frames >= self.config.motion_detection.frames:
                if not self.motion_detected:
                    self.motion_detected = True
                return
        else:
            self._motion_frames = 0

        if self.motion_detected:
            self.motion_detected = False

    @property
    def motion_detected(self):
        return self._motion_detected

    @motion_detected.setter
    def motion_detected(self, motion_detected):
        self._motion_detected = motion_detected
        self._motion_logger.debug(
            "Motion detected" if motion_detected else "Motion stopped"
        )

        if self._mqtt.mqtt_queue:
            self._mqtt.devices["motion_detected"].publish(motion_detected)

    def process_object_event(self, frame):
        if self._trigger_recorder or any(zone.trigger_recorder for zone in self._zones):
            if not self.recorder.is_recording:
                draw_objects(
                    frame.decoded_frame_umat_rgb,
                    self.objects_in_fov,
                    self.camera.resolution,
                )
                self.start_recording(frame)

    def process_motion_event(self):
        if self.motion_detected:
            if (
                self.config.motion_detection.trigger_detector
                and not self.camera.scan_for_objects.is_set()
            ):
                self.camera.scan_for_objects.set()
                self._logger.debug("Starting object detector")
        elif (
            self.camera.scan_for_objects.is_set()
            and not self.recorder.is_recording
            and self.config.motion_detection.trigger_detector
        ):
            self._logger.debug("Not recording, pausing object detector")
            self.camera.scan_for_objects.clear()

    def run(self):
        """ Main thread. It handles starting/stopping of recordings and
        publishes to MQTT if object is detected. Speed is determined by FPS"""
        self._logger.debug("Waiting for first frame")
        self.camera.frame_ready.wait()
        self._logger.debug("First frame received")

        self.idle_frames = 0
        while not self.kill_received:
            self.camera.frame_ready.wait()

            # Filter returned objects
            processed_object_frame = self.get_processed_object_frame()
            if processed_object_frame:
                if self._object_logger.level == LOG_LEVELS["DEBUG"]:
                    self._object_logger.debug(
                        f"Objects: "
                        f"{[obj.formatted for obj in processed_object_frame.objects]}"
                    )
                # Filter objects in the FoV
                self.filter_fov(processed_object_frame)
                # Filter objects in each zone
                self.filter_zones(processed_object_frame)

            # Filter returned motion contours
            processed_motion_frame = self.get_processed_motion_frame()
            if processed_motion_frame:
                # self._logger.debug(processed_motion_frame.motion_contours)
                self.filter_motion(processed_motion_frame.motion_contours)

            self.process_object_event(processed_object_frame)
            self.process_motion_event()

            if (
                processed_object_frame or processed_motion_frame
            ) and self.config.camera.publish_image:
                self._mqtt.publish_image(
                    processed_object_frame,
                    processed_motion_frame,
                    self._zones,
                    self.camera.resolution,
                )

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
        self.camera.release()
        self.camera_grabber.join()
