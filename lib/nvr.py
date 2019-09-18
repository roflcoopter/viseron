import logging
from threading import Thread, Event
from queue import Queue

import config
from lib.camera import FFMPEGCamera
from lib.detector import Detector
from lib.recorder import FFMPEGRecorder
from lib.motion import MotionDetection

LOGGER = logging.getLogger(__name__)


class FFMPEGNVR(object):
    def __init__(self, mqtt, frame_buffer):
        LOGGER.info('Initializing NVR thread')
        self.kill_received = False
        self.frame_ready = Event()
        self.object_event = Event()  # Triggered when object detected
        self.scan_for_objects = Event()  # Set when frame should be scanned
        self.motion_event = Event()  # Triggered when motion detected
        self.scan_for_motion = Event()  # Set when frame should be scanned
        self.recorder_thread = None

        if config.MOTION_DETECTION_TRIGGER:
            self.scan_for_motion.set()
            self.scan_for_objects.clear()
        else:
            self.scan_for_objects.set()
            self.scan_for_motion.clear()

        object_decoder_queue = Queue(maxsize=2)
        motion_decoder_queue = Queue(maxsize=2)
        motion_queue = Queue(maxsize=2)
        detector_queue = Queue(maxsize=2)

        # Use FFMPEG to read from camera. Used for reading/recording
        self.ffmpeg = FFMPEGCamera(frame_buffer)

        # Object detector class. Called every config.OBJECT_DETECTION_INTERVAL
        self.detector = Detector(self.ffmpeg, mqtt, self.object_event)
        self.ffmpeg.detector = self.detector
        self.detector_thread = Thread(target=self.detector.object_detection,
                                      args=(detector_queue,))
        self.detector_thread.daemon = True

        # Motion detector class.
        if config.MOTION_DETECTION_TIMEOUT or config.MOTION_DETECTION_TRIGGER:
            self.motion_detector = MotionDetection(self.motion_event,
                                                   config.MIN_MOTION_AREA,
                                                   config.MOTION_FRAMES)
            self.motion_thread = Thread(target=self.motion_detector.motion_detection,
                                        args=(motion_queue,))
            self.motion_thread.daemon = True
            self.motion_thread.start()

            self.motion_decoder = Thread(
                target=self.ffmpeg.decoder,
                args=(motion_decoder_queue,
                      motion_queue,
                      config.MOTION_DETECTION_WIDTH,
                      config.MOTION_DETECTION_HEIGHT))
            self.motion_decoder.daemon = True
            self.motion_decoder.start()

        # Start a process to pipe ffmpeg output
        self.ffmpeg_grabber = Thread(target=self.ffmpeg.capture_pipe,
                                     args=(frame_buffer,
                                           self.frame_ready,
                                           config.OBJECT_DETECTION_INTERVAL,
                                           object_decoder_queue,
                                           self.scan_for_objects,
                                           config.MOTION_DETECTION_INTERVAL,
                                           motion_decoder_queue,
                                           self.scan_for_motion))
        self.ffmpeg_grabber.daemon = True

        self.ffmpeg_decoder = Thread(
            target=self.ffmpeg.decoder,
            args=(object_decoder_queue,
                  detector_queue,
                  config.OBJECT_DETECTION_MODEL_WIDTH,
                  config.OBJECT_DETECTION_MODEL_HEIGHT))
        self.ffmpeg_decoder.daemon = True

        self.ffmpeg_grabber.start()
        self.ffmpeg_decoder.start()
        self.detector_thread.start()

        # Initialize recorder
        self.Recorder = FFMPEGRecorder()
        # Detector and Recorder are both dependant on eachother
        self.detector.Recorder = self.Recorder
        LOGGER.info('NVR thread initialized')

    def event_over(self):
        if self.object_event.is_set():
            return False
        if config.MOTION_DETECTION_TIMEOUT and self.motion_event.is_set():
            return False
        return True

    def run(self, mqtt, frame_buffer):
        """ Main thread. It handles starting/stopping of recordings and
        publishes to MQTT if object is detected. Speed is determined by FPS"""
        LOGGER.info('Starting main loop')

        idle_frames = 0

        # Continue til we get kill command from root thread
        while not self.kill_received:
            self.frame_ready.wait(10)
            if self.motion_event.is_set():
                idle_frames = 0
                if config.MOTION_DETECTION_TRIGGER \
                and not self.scan_for_objects.is_set():
                    self.scan_for_objects.set()
                    LOGGER.debug("Motion detected! Starting object detector")
            elif self.scan_for_objects.is_set() and not self.Recorder.is_recording and config.MOTION_DETECTION_TRIGGER:
                LOGGER.debug("Not recording, pausing object detector")
                self.scan_for_objects.clear()

            # Start recording
            if self.object_event.is_set():
                idle_frames = 0
                if not self.Recorder.is_recording:
                    mqtt.publish_sensor(True, self.detector.filtered_objects)
                    self.recorder_thread = \
                        Thread(target=self.Recorder.start_recording,
                               args=(frame_buffer,
                                     self.ffmpeg.stream_width,
                                     self.ffmpeg.stream_height,
                                     self.ffmpeg.stream_fps))
                    self.recorder_thread.start()
                    if config.MOTION_DETECTION_TIMEOUT:
                        self.scan_for_motion.set()
                        LOGGER.info("Starting motion detector")
                    continue

            # If we are recording and no object is detected
            if self.Recorder.is_recording and self.event_over():
                idle_frames += 1
                if idle_frames % self.ffmpeg.stream_fps == 0:
                    LOGGER.info('Stopping recording in: {}'
                                .format(int(config.RECORDING_TIMEOUT -
                                            (idle_frames /
                                             self.ffmpeg.stream_fps))))

                if idle_frames >= (self.ffmpeg.stream_fps *
                                   config.RECORDING_TIMEOUT):

                    mqtt.publish_sensor(False, self.detector.filtered_objects)
                    self.detector.tracking = False
                    self.Recorder.stop()
                    if config.MOTION_DETECTION_TRIGGER:
                        self.scan_for_objects.clear()
                        LOGGER.info("Pausing object detector")
                    else:
                        self.scan_for_motion.clear()
                        LOGGER.info("Pausing motion detector")
        LOGGER.info("Exiting NVR thread")

    def stop(self):
        LOGGER.info('Stopping NVR thread')
        self.kill_received = True
        # Stop the detector timer thread(s)
        self.detector.stop()

        # Stop potential recording
        if self.Recorder.is_recording:
            self.Recorder.stop()
            self.recorder_thread.join()

        # Stop frame grabber
        self.ffmpeg.release()
        self.ffmpeg_grabber.join()
