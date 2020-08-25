import json
import logging
from queue import Empty, Queue
from threading import Event, Thread
from typing import List

import cv2
from lib.camera import FFMPEGCamera
from lib.helpers import draw_bounding_box_relative
from lib.motion import MotionDetection
from lib.recorder import FFMPEGRecorder

LOGGER = logging.getLogger(__name__)


class FFMPEGNVR(Thread):
    nvr_list: List[object] = []

    def __init__(self, config, detector, detector_queue, mqtt_queue=None):
        Thread.__init__(self)
        self.nvr_list.append({config.camera.mqtt_name: self})
        LOGGER.info("Initializing NVR thread")
        self.kill_received = False
        self.frame_ready = Event()
        self.object_event = Event()  # Triggered when object detected
        self.scan_for_objects = Event()  # Set when frame should be scanned
        self.motion_event = Event()  # Triggered when motion detected
        self.scan_for_motion = Event()  # Set when frame should be scanned
        self.mqtt_queue = mqtt_queue
        self.config = config
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
                self.object_event,
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
        LOGGER.info("NVR thread initialized")

    def event_over(self):
        if self.object_event.is_set():
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
            LOGGER.info("Starting motion detector")

    def stop_recording(self):
        if self.idle_frames % self.ffmpeg.stream_fps == 0:
            LOGGER.info(
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
            with self.object_return_queue.mutex:  # Clear any objects left in queue
                self.object_return_queue.queue.clear()

            if self.config.motion_detection.trigger:
                self.scan_for_objects.clear()
                LOGGER.info("Pausing object detector")
            else:
                self.scan_for_motion.clear()
                LOGGER.info("Pausing motion detector")

    def get_detected_objects(self):
        """ Returns a frame along with its detections
        If no frame is in the queue, return the most recently decoded frame """
        try:
            return self.object_return_queue.get_nowait()
        except Empty:
            pass
        return {"frame": None, "full_frame": self.ffmpeg.current_frame, "objects": []}

    def draw_objects(self, frame, objects):
        """ Draws objects on supplied frame """
        for obj in objects:
            frame = draw_bounding_box_relative(
                frame,
                (
                    obj["relative_x1"],
                    obj["relative_y1"],
                    obj["relative_x2"],
                    obj["relative_y2"],
                ),
                self.ffmpeg.resolution,
            )
        return frame

    def run(self):
        """ Main thread. It handles starting/stopping of recordings and
        publishes to MQTT if object is detected. Speed is determined by FPS"""
        LOGGER.info("Starting main loop")
        LOGGER.debug("Waiting for first frame")
        self.frame_ready.wait()
        LOGGER.debug("First frame received")

        self.idle_frames = 0
        # Continue til we get kill command from root thread
        while not self.kill_received:
            if not self.frame_ready.wait(2):
                LOGGER.error("Timeout waiting for frame")
                continue

            if self.motion_event.is_set():
                self.idle_frames = 0
                if (
                    self.config.motion_detection.trigger
                    and not self.scan_for_objects.is_set()
                ):
                    self.scan_for_objects.set()
                    LOGGER.debug("Motion detected! Starting object detector")
            elif (
                self.scan_for_objects.is_set()
                and not self.recorder.is_recording
                and self.config.motion_detection.trigger
            ):
                LOGGER.debug("Not recording, pausing object detector")
                self.scan_for_objects.clear()

            # Object Detected
            if self.object_event.is_set():
                self.idle_frames = 0
                if not self.recorder.is_recording:
                    detected_objects = self.get_detected_objects()
                    self.publish_sensor(True, [])
                    thumbnail = self.draw_objects(
                        detected_objects["full_frame"], detected_objects["objects"]
                    )
                    self.start_recording(thumbnail)
                continue

            # If we are recording and no object is detected
            if self.recorder.is_recording and self.event_over():
                self.idle_frames += 1
                self.stop_recording()

        LOGGER.info("Exiting NVR thread")

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

        subscriptions = []
        subscriptions.append(
            {"topic": self.mqtt_switch_command_topic, "callback": self.on_message}
        )
        self.publish_sensor(False)

        return subscriptions

    def on_message(self, message):
        LOGGER.debug(message.payload.decode())
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
        return json.dumps(payload, indent=3)

    @property
    def mqtt_switch_command_topic(self):
        return f"{self.config.mqtt.discovery_prefix}/switch/{self.config.camera.mqtt_name}/set"

    @property
    def mqtt_switch_state_topic(self):
        return f"{self.config.mqtt.discovery_prefix}/switch/{self.config.camera.mqtt_name}/state"

    @property
    def mqtt_switch_config_topic(self):
        return f"{self.config.mqtt.discovery_prefix}/switch/{self.config.camera.mqtt_name}/config"

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
        return f"{self.config.mqtt.discovery_prefix}/sensor/{self.config.camera.mqtt_name}/state"

    @property
    def mqtt_sensor_config_topic(self):
        return f"{self.config.mqtt.discovery_prefix}/sensor/{self.config.camera.mqtt_name}/config"

    @property
    def mqtt_camera_config_payload(self):
        payload = {}
        payload["name"] = self.config.camera.mqtt_name
        payload["topic"] = self.mqtt_camera_state_topic
        return json.dumps(payload, indent=3)

    @property
    def mqtt_camera_state_topic(self):
        return f"{self.config.mqtt.discovery_prefix}/camera/{self.config.camera.mqtt_name}/image"

    @property
    def mqtt_camera_config_topic(self):
        return f"{self.config.mqtt.discovery_prefix}/camera/{self.config.camera.mqtt_name}/config"

    def publish_sensor(self, object_detected, detections=None):
        if self.mqtt_queue:
            payload = {}
            payload["state"] = "on" if object_detected else "off"
            payload["detections"] = detections
            json_payload = json.dumps(payload, indent=3)

            self.mqtt_queue.put(
                {"topic": self.mqtt_sensor_state_topic, "payload": json_payload}
            )

    def publish_image(self, frame):
        if self.mqtt_queue:
            ret, jpg = cv2.imencode(".jpg", frame)
            if ret:
                self.mqtt_queue.put(
                    {"topic": self.mqtt_camera_state_topic, "payload": jpg.tobytes()}
                )

    def stop(self):
        LOGGER.info("Stopping NVR thread")
        self.kill_received = True

        # Stop potential recording
        if self.recorder.is_recording:
            self.recorder.stop()
            self.recorder_thread.join()

        # Stop frame grabber
        self.ffmpeg.release()
        self.ffmpeg_grabber.join()
