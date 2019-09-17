import logging
import threading
from queue import Queue

import config
from lib.camera import FFMPEGCamera
from lib.detector import Detector
from lib.recorder import FFMPEGRecorder

LOGGER = logging.getLogger(__name__)


class FFMPEGNVR(object):
    def __init__(self, mqtt, frame_buffer):
        LOGGER.info('Initializing NVR thread')
        self.kill_received = False
        self.frame_ready = threading.Event()
        self.object_event = threading.Event()
        self.motion_event = threading.Event()
        self.recorder_thread = None

        decoded_frame_buffer = Queue(maxsize=100)

        decoder_queue = Queue(maxsize=1)
        detector_queue = Queue(maxsize=1)

        # Use FFMPEG to read from camera. Used for reading/recording
        self.ffmpeg = FFMPEGCamera(frame_buffer)
        # Object detector class. Called every config.OBJECT_DETECTION_INTERVAL
        self.detector = Detector(self.ffmpeg, mqtt, self.object_event, self.motion_event, detector_queue)
        self.ffmpeg.detector = self.detector

        # Start a process to pipe ffmpeg output
        self.ffmpeg_grabber = threading.Thread(target=self.ffmpeg.capture_pipe,
                                               args=(frame_buffer,
                                                     self.frame_ready,
                                                     decoder_queue))

        self.ffmpeg_decoder = threading.Thread(
            target=self.ffmpeg.decoder,
            args=(decoder_queue,
                  detector_queue,
                  config.OBJECT_DETECTION_MODEL_WIDTH,
                  config.OBJECT_DETECTION_MODEL_HEIGHT))

        self.ffmpeg_grabber.daemon = True
        self.ffmpeg_decoder.daemon = True
        self.ffmpeg_grabber.start()
        self.ffmpeg_decoder.start()

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
        publishes to MQTT of object is detected. Speed is determined by FPS"""
        LOGGER.info('Starting main loop')

        idle_frames = 0

        # Continue til we get kill command from root thread
        while not self.kill_received:
            self.frame_ready.wait(10)
            if self.motion_event.is_set():
                idle_frames = 0
            # Start recording
            if self.object_event.is_set():
                idle_frames = 0
                if not self.Recorder.is_recording:
                    mqtt.publish_sensor(True, self.detector.filtered_objects)
                    self.recorder_thread = \
                        threading.Thread(target=self.Recorder.start_recording,
                                         args=(frame_buffer,
                                               self.ffmpeg.stream_width,
                                               self.ffmpeg.stream_height,
                                               self.ffmpeg.stream_fps))
                    self.recorder_thread.start()
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
                        self.detector.scheduler.pause_job('object_detector')
                        LOGGER.info("Pausing object detector")
                    else:
                        self.detector.scheduler.pause_job('motion_detector')
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
