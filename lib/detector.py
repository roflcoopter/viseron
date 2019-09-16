import logging
from datetime import datetime
import config
import cv2
import imutils
import os
import threading
from queue import Queue, Empty, Full
from apscheduler.schedulers.background import BackgroundScheduler
from operator import sub
from lib.motion_detection import MotionDetection
from lib import deeplab_overlay

LOGGER = logging.getLogger(__name__)


class Detector(object):
    def __init__(self, Camera, mqtt, detection_lock, image_processing_buffer,
                 decoded_frame_buffer, frame_ready):
        LOGGER.info('Initializing detection thread')

        # Make the logging of apscheduler less verbose
        logging.getLogger(
            'apscheduler.executors.default').setLevel(logging.ERROR)
        logging.getLogger('apscheduler.scheduler').setLevel(logging.ERROR)

        # Activate OpenCL
        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(True)

        self._object_detected = False
        self.filtered_objects = []
        self.detection_lock = detection_lock
        self.image_processing_buffer = image_processing_buffer
        self.decoded_frame_buffer = decoded_frame_buffer

        self.motion_detector = MotionDetection()
        self.motion_detected = False
        self.motion_frames = 0
        self.motion_area = 0

        self.tracking = False
        self.tracking_successful = False
        self.frame_ready = frame_ready

        self.Camera = Camera
        self.mqtt = mqtt
        self.Recorder = None

        if config.OBJECT_DETECTION_TYPE == "edgetpu":
            from lib.edgetpu_detection import ObjectDetection
            self.ObjectDetection = \
                ObjectDetection(model=config.OBJECT_DETECTION_MODEL,
                                labels=config.OBJECT_DETECTION_LABELS_FILE,
                                threshold=config.OBJECT_DETECTION_THRESH,
                                camera_res=(Camera.stream_width,
                                            Camera.stream_height))
        elif config.OBJECT_DETECTION_TYPE == "efficientnet":
            from lib.edgetpu_classification import ObjectClassification
            self.ObjectDetection = \
                ObjectClassification(model=config.OBJECT_DETECTION_MODEL,
                                labels=config.OBJECT_DETECTION_LABELS_FILE,
                                threshold=config.OBJECT_DETECTION_THRESH,
                                camera_res=(Camera.stream_width,
                                            Camera.stream_height))
        elif config.OBJECT_DETECTION_TYPE == "deeplab":
            from lib.deeplab_detection import DeeplabDetection
            self.ObjectDetection = \
                DeeplabDetection(model=config.OBJECT_DETECTION_MODEL,
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
        # Get the most recently grabbed frame
        with self.detection_lock:
            grabbed, current_frame = self.Camera.current_frame_resized(
                config.OBJECT_DETECTION_MODEL_WIDTH,
                config.OBJECT_DETECTION_MODEL_HEIGHT)

            self.filtered_objects = []

            if grabbed:
                objects = self.ObjectDetection.return_objects(current_frame)
                for obj in objects:
                    cv2.rectangle(current_frame,
                                  (int(obj["unscaled_x1"]), int(obj["unscaled_y1"])),
                                  (int(obj["unscaled_x2"]), int(obj["unscaled_y2"])),
                                  (255, 0, 0), 5)
                    self.mqtt.publish_image(current_frame)

                self.filtered_objects = list(
                    filter(self.filter_objects, objects))

                if self.filtered_objects:
                    LOGGER.info(self.filtered_objects)
                    if not self.object_detected:
                        self.object_detected = True
                    return
            else:
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
            if config.MOTION_DETECTION_TIMEOUT:
                self.scheduler.resume_job('motion_detector')
                self.scheduler.modify_job(job_id='motion_detector',
                                          next_run_time=datetime.utcnow())
                LOGGER.info("Object detected! Starting motion detector")

            if config.OBJECT_TRACKING_TIMEOUT:
                if not self.tracking:
                    self.tracking = True
                    decoder_thread = \
                        threading.Thread(target=self.Camera.decoder, args=[])
                    decoder_thread.start()
                    tracker_thread = \
                        threading.Thread(target=self.track_objects, args=[])
                    tracker_thread.start()

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
                    if config.MOTION_DETECTION_TRIGGER:
                        self.scheduler.resume_job('object_detector')
                        self.scheduler.modify_job(
                            job_id='object_detector',
                            next_run_time=datetime.utcnow())
                        LOGGER.debug(
                            "Motion detected! Starting object detector")
                return
        elif self.motion_detected:
            self.motion_frames -= 1
        else:
            self.motion_frames = 0

        if self.motion_detected:
            self.motion_detected = False
            LOGGER.debug("Motion has ended")
            if not self.object_detected and not self.Recorder.is_recording and config.MOTION_DETECTION_TRIGGER:
                LOGGER.debug("Not recording, pausing object detector")
                self.scheduler.pause_job('object_detector')

    def abs_sub(self, x, y):
        return abs(x - y)

    def track_objects(self):
        LOGGER.info("Starting tracker thread")

        trackers = []

        while self.tracking:
            frame = self.decoded_frame_buffer.get()
            tracker = cv2.TrackerKCF_create()

            if frame['trackable_objects']:
                objects = frame['trackable_objects']
                trackers = []
                for obj in objects:
                    bounding_box = (obj["x1"],
                                    obj["y1"],
                                    obj["x2"],
                                    obj["y2"])
                    try:
                        tracker.init(frame['frame'], bounding_box)
                        trackers.append({'tracker': tracker,
                                         'old_box': bounding_box})
                        LOGGER.info("Setup new tracker for object at {}"
                                    .format(bounding_box))
                    except cv2.error as error:
                        LOGGER.error("Failed to setup tracker for {}"
                                     .format(bounding_box))
                        LOGGER.error(error)

            for tracker in trackers:
                success, new_box = tracker['tracker'].update(frame['frame'])
                cv2.rectangle(frame['frame'],
                              (int(new_box[0]), int(new_box[1])),
                              (int(new_box[2]), int(new_box[3])),
                              (255, 0, 0), 5)

                if success:
                    movement = tuple(
                        map(self.abs_sub, new_box, tracker['old_box']))
                    LOGGER.info("old_box: {}, new_box: {}, movement: {}"
                                .format(tracker['old_box'], new_box, movement))

                    self.tracking_successful = bool(any(i > config.OBJECT_TRACKING_THRESH for i in movement))
                    tracker['old_box'] = new_box
                else:
                    LOGGER.info("Object lost")
                    self.tracking_successful = False

            self.mqtt.publish_image(frame['frame'])

        LOGGER.info("Exiting tracker thread")

    def stop(self):
        self.object_detected = False
        self.motion_detected = False
        self.tracking = False
        self.scheduler.shutdown()
        return
