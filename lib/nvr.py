import logging
from threading import Thread, Event
from queue import Queue, Empty

from lib.camera import FFMPEGCamera
from lib.detector import Detector
from lib.recorder import FFMPEGRecorder
from lib.motion import MotionDetection

LOGGER = logging.getLogger(__name__)


class FFMPEGNVR(Thread):
    def __init__(self, mqtt, config):
        LOGGER.info("Initializing NVR thread")
        Thread.__init__(self)
        self.kill_received = False
        self.frame_ready = Event()
        self.object_event = Event()  # Triggered when object detected
        self.scan_for_objects = Event()  # Set when frame should be scanned
        self.motion_event = Event()  # Triggered when motion detected
        self.scan_for_motion = Event()  # Set when frame should be scanned
        self.recorder_thread = None
        self.mqtt = mqtt
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
        detector_queue = Queue(maxsize=2)
        self.object_return_queue = Queue(maxsize=20)

        # Use FFMPEG to read from camera. Used for reading/recording
        # Maxsize changes later based on config option LOOKBACK_SECONDS
        frame_buffer = Queue(maxsize=1)
        self.ffmpeg = FFMPEGCamera(self.config, frame_buffer)

        # Object detector class. Called every config.OBJECT_DETECTION_INTERVAL
        self.detector = Detector(self.ffmpeg)
        self.detector_thread = Thread(
            target=self.detector.object_detection, args=(detector_queue,)
        )
        self.detector_thread.daemon = True

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
                self.config.object_detection.model_width,
                self.config.object_detection.model_height,
            ),
        )
        self.ffmpeg_decoder.daemon = True

        self.ffmpeg_grabber.start()
        self.ffmpeg_decoder.start()
        self.detector_thread.start()

        # Initialize recorder
        self.Recorder = FFMPEGRecorder(self.config, frame_buffer)
        LOGGER.info("NVR thread initialized")

    def event_over(self):
        if self.object_event.is_set():
            return False
        if self.config.motion_detection.timeout and self.motion_event.is_set():
            return False
        return True

    def start_recording(self):
        self.recorder_thread = Thread(
            target=self.Recorder.start_recording,
            args=(
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
            self.mqtt.publish_sensor(False, [])
            self.Recorder.stop()
            if self.config.motion_detection.trigger:
                self.scan_for_objects.clear()
                LOGGER.info("Pausing object detector")
            else:
                self.scan_for_motion.clear()
                LOGGER.info("Pausing motion detector")

    def publish_objects(self):
        try:
            returned_objects = self.object_return_queue.get_nowait()
            for obj in returned_objects["objects"]:
                cv2.rectangle(
                    returned_objects["frame"],
                    (int(obj["unscaled_x1"]), int(obj["unscaled_y1"])),
                    (int(obj["unscaled_x2"]), int(obj["unscaled_y2"])),
                    (255, 0, 0),
                    5,
                )
                self.mqtt.publish_image(returned_objects["frame"])
        except Empty:
            pass

    def run(self):
        """ Main thread. It handles starting/stopping of recordings and
        publishes to MQTT if object is detected. Speed is determined by FPS"""
        LOGGER.info("Starting main loop")

        self.idle_frames = 0
        # Continue til we get kill command from root thread
        while not self.kill_received:
            try:
                self.frame_ready.wait(2)
            except:
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
                and not self.Recorder.is_recording
                and self.config.motion_detection.trigger
            ):
                LOGGER.debug("Not recording, pausing object detector")
                self.scan_for_objects.clear()

            # Object Detected
            if self.object_event.is_set():
                self.idle_frames = 0
                if not self.Recorder.is_recording:
                    self.mqtt.publish_sensor(True, [])
                    self.start_recording()

                self.publish_objects()
                continue

            # If we are recording and no object is detected
            if self.Recorder.is_recording and self.event_over():
                self.idle_frames += 1
                self.stop_recording()

        LOGGER.info("Exiting NVR thread")

    def stop(self):
        LOGGER.info("Stopping NVR thread")
        self.kill_received = True

        # Stop potential recording
        if self.Recorder.is_recording:
            self.Recorder.stop()
            self.recorder_thread.join()

        # Stop frame grabber
        self.ffmpeg.release()
        self.ffmpeg_grabber.join()
