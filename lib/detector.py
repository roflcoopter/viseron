import logging
from datetime import datetime
import config
import cv2
import imutils
import os
import threading
from queue import Queue, Empty, Full

LOGGER = logging.getLogger(__name__)


class Detector(object):
    def __init__(self, Camera, mqtt, object_event):
        LOGGER.info('Initializing detection thread')

        # Activate OpenCL
        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(True)

        self.Camera = Camera
        self.mqtt = mqtt
        self.Recorder = None

        self._object_detected = False
        self.filtered_objects = []
        self.object_event = object_event

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

    def filter_objects(self, result):
        if result['label'] in config.OBJECT_DETECTION_LABELS \
        and config.OBJECT_DETECTION_HEIGHT_MIN <= result['height'] <= config.OBJECT_DETECTION_HEIGHT_MAX \
        and config.OBJECT_DETECTION_WIDTH_MIN <= result['width'] <= config.OBJECT_DETECTION_WIDTH_MAX:
            return True
        return False

    def object_detection(self, detector_queue):
        while True:
            self.filtered_objects = []

            try:
                frame = detector_queue.get()

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
                    continue
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
        else:
            self.object_event.clear()

    def stop(self):
        self.object_detected = False
        return
