import logging
from datetime import datetime
import config
import cv2
import imutils
import os
import threading
from queue import Queue, Empty, Full
from apscheduler.schedulers.background import BackgroundScheduler
from lib.motion_detection import MotionDetection

LOGGER = logging.getLogger(__name__)


class Detector(object):
    def __init__(self, Camera, mqtt, object_event, motion_event, detector_queue):
        LOGGER.info('Initializing detection thread')

        # Make the logging of apscheduler less verbose
        logging.getLogger(
            'apscheduler.executors.default').setLevel(logging.ERROR)
        logging.getLogger('apscheduler.scheduler').setLevel(logging.ERROR)

        # Activate OpenCL
        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(True)

        self.Camera = Camera
        self.mqtt = mqtt
        self.Recorder = None

        self._object_detected = False
        self.filtered_objects = []
        self.object_event = object_event
        self.detector_queue = detector_queue

        self._motion_detected = False
        self.motion_detector = MotionDetection()
        self.motion_frames = 0
        self.motion_area = 0
        self.motion_event = motion_event

        if config.OBJECT_DETECTION_TYPE == "edgetpu":
            from lib.edgetpu_detection import ObjectDetection
            self.ObjectDetection = \
                ObjectDetection(model=config.OBJECT_DETECTION_MODEL,
                                labels=config.OBJECT_DETECTION_LABELS_FILE,
                                threshold=config.OBJECT_DETECTION_THRESH,
                                camera_res=(Camera.stream_width,
                                            Camera.stream_height))
        elif config.OBJECT_DETECTION_TYPE == "darknet":
            from lib.darknet_detection import ObjectDetection
            self.ObjectDetection = \
                ObjectDetection(input=None,
                                model=config.OBJECT_DETECTION_MODEL,
                                config=config.OBJECT_DETECTION_CONFIG,
                                classes=config.OBJECT_DETECTION_LABELS_FILE,
                                thr=config.OBJECT_DETECTION_THRESH,
                                nms=config.OBJECT_DETECTION_NMS,
                                camera_res=(Camera.stream_width,
                                            Camera.stream_height))
        elif config.OBJECT_DETECTION_TYPE == "posenet":
            from lib.posenet_detection import ObjectDetection
            self.ObjectDetection = \
                ObjectDetection(model=config.OBJECT_DETECTION_MODEL,
                                threshold=config.OBJECT_DETECTION_THRESH,
                                model_res=(config.OBJECT_DETECTION_MODEL_WIDTH,
                                           config.OBJECT_DETECTION_MODEL_HEIGHT),
                                camera_res=(Camera.stream_width,
                                            Camera.stream_height))
        else:
            LOGGER.error("OBJECT_DETECTION_TYPE has to be "
                         "either \"edgetpu\", \"darknet\" or \"posenet\"")
            return

        self.scheduler = BackgroundScheduler(timezone='UTC')
        self.scheduler.start()
        self.scheduler.add_job(self.object_detection,
                               'interval',
                               seconds=config.OBJECT_DETECTION_INTERVAL,
                               id='object_detector',
                               next_run_time=datetime.utcnow())

        self.scheduler.add_job(self.motion_detection,
                               'interval',
                               seconds=config.MOTION_DETECTION_INTERVAL,
                               id='motion_detector',
                               next_run_time=datetime.utcnow())

        if config.MOTION_DETECTION_TRIGGER:
            self.scheduler.pause_job('object_detector')
        else:
            self.scheduler.pause_job('motion_detector')

    def filter_objects(self, result):
        if result['label'] in config.OBJECT_DETECTION_LABELS \
        and config.OBJECT_DETECTION_HEIGHT_MIN <= result['height'] <= config.OBJECT_DETECTION_HEIGHT_MAX \
        and config.OBJECT_DETECTION_WIDTH_MIN <= result['width'] <= config.OBJECT_DETECTION_WIDTH_MAX:
            return True
        return False

    def object_detection(self):
        self.filtered_objects = []

        try:
            frame = self.detector_queue.get_nowait()

            objects = self.ObjectDetection.return_objects(frame['frame'])
            for obj in objects:
                cv2.rectangle(frame['frame'],
                              (int(obj["unscaled_x1"]),
                               int(obj["unscaled_y1"])),
                              (int(obj["unscaled_x2"]),
                               int(obj["unscaled_y2"])),
                              (255, 0, 0), 5)
                self.mqtt.publish_image(frame['frame'])

            self.filtered_objects = list(
                filter(self.filter_objects, objects))

            if self.filtered_objects:
                LOGGER.info(self.filtered_objects)
                if not self.object_detected:
                    self.object_detected = True
                return
        except Empty:
            LOGGER.error('Frame not grabbed for object detection')

        if self.object_detected:
            self.object_detected = False

    @property
    def object_detected(self):
        return self._object_detected

    @object_detected.setter
    def object_detected(self, _object_detected):
        self._object_detected = _object_detected

        if _object_detected:
            self.object_event.set()
            if config.MOTION_DETECTION_TIMEOUT:
                self.scheduler.resume_job('motion_detector')
                self.scheduler.modify_job(job_id='motion_detector',
                                          next_run_time=datetime.utcnow())
                LOGGER.info("Object detected! Starting motion detector")
        else:
            self.object_event.clear()

    # @profile
    def motion_detection(self):
        # resize the frame, convert it to grayscale, and blur it
        grabbed, frame = self.Camera.current_frame_resized(
            config.MOTION_DETECTION_WIDTH,
            config.MOTION_DETECTION_HEIGHT)

        if grabbed:
            max_contour = self.motion_detector.detect(frame)
        else:
            LOGGER.error('Frame not grabbed for motion detector')
            return

        if max_contour > config.MIN_MOTION_AREA:
            self.motion_area = max_contour
            _motion_found = True
        else:
            _motion_found = False

        if _motion_found:
            self.motion_frames += 1
            LOGGER.debug("Motion frames: {}, "
                         "area: {}".format(self.motion_frames, max_contour))

            if self.motion_frames >= config.MOTION_FRAMES:
                self.motion_frames = config.MOTION_FRAMES
                if not self.motion_detected:
                    self.motion_detected = True
                return
        else:
            self.motion_frames = 0

        if self.motion_detected:
            self.motion_detected = False

    @property
    def motion_detected(self):
        return self._motion_detected

    @motion_detected.setter
    def motion_detected(self, _motion_detected):
        self._motion_detected = _motion_detected

        if _motion_detected:
            self.motion_event.set()
            if config.MOTION_DETECTION_TRIGGER:
                self.scheduler.resume_job('object_detector')
                self.scheduler.modify_job(
                    job_id='object_detector',
                    next_run_time=datetime.utcnow())
                LOGGER.debug(
                    "Motion detected! Starting object detector")
        else:
            LOGGER.debug("Motion has ended")
            self.motion_event.clear()
            if not self.object_detected and not self.Recorder.is_recording and config.MOTION_DETECTION_TRIGGER:
                LOGGER.debug("Not recording, pausing object detector")
                self.scheduler.pause_job('object_detector')

    def stop(self):
        self.object_detected = False
        self.motion_detected = False
        self.scheduler.shutdown()
        return
