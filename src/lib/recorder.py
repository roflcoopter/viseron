import datetime
import logging
import os
from threading import Thread

import cv2

from lib.cleanup import SegmentCleanup
from lib.helpers import draw_objects
from lib.mqtt.camera import MQTTCamera
from lib.segments import Segments

LOGGER = logging.getLogger(__name__)


class FFMPEGRecorder:
    def __init__(self, config, detection_lock, mqtt_queue):
        self._logger = logging.getLogger(__name__ + "." + config.camera.name_slug)
        if getattr(config.recorder.logging, "level", None):
            self._logger.setLevel(config.recorder.logging.level)
        elif getattr(config.camera.logging, "level", None):
            self._logger.setLevel(config.camera.logging.level)
        self._logger.debug("Initializing ffmpeg recorder")
        self.config = config
        self._mqtt_queue = mqtt_queue

        self.is_recording = False
        self.last_recording_start = None
        self.last_recording_end = None
        self._event_start = None
        self._event_end = None
        self._recording_name = None

        segments_folder = os.path.join(
            config.recorder.segments_folder, config.camera.name
        )
        self.create_directory(segments_folder)
        self._segmenter = Segments(
            self._logger, config, segments_folder, detection_lock
        )
        self._segment_cleanup = SegmentCleanup(config)

        self._mqtt_devices = {}
        if self.config.recorder.thumbnail.send_to_mqtt:
            self._mqtt_devices["latest_thumbnail"] = MQTTCamera(
                config, mqtt_queue, object_id="latest_thumbnail"
            )

    def on_connect(self, client):
        for device in self._mqtt_devices.values():
            device.on_connect(client)

    def subfolder_name(self, today):
        return (
            f"{today.year:04}-{today.month:02}-{today.day:02}/{self.config.camera.name}"
        )

    def create_thumbnail(self, file_name, frame, objects, resolution):
        draw_objects(
            frame.decoded_frame_umat_rgb, objects, resolution,
        )
        cv2.imwrite(file_name, frame.decoded_frame_umat_rgb)

        if self.config.recorder.thumbnail.save_to_disk:
            thumbnail_folder = os.path.join(
                self.config.recorder.folder,
                "thumbnails",
                self.config.camera.name,
                "latest_thumbnail.jpg",
            )
            self.create_directory(thumbnail_folder)

            self._logger.debug(f"Saving thumbnail in {thumbnail_folder}")
            if not cv2.imwrite(
                os.path.join(thumbnail_folder, "latest_thumbnail.jpg"),
                frame.decoded_frame_umat_rgb,
            ):
                self._logger.error("Failed saving thumbnail to disk")

        if self.config.recorder.thumbnail.send_to_mqtt and self._mqtt_devices:
            ret, jpg = cv2.imencode(".jpg", frame.decoded_frame_umat_rgb)
            if ret:
                self._mqtt_devices["latest_thumbnail"].publish(jpg.tobytes())

    def create_directory(self, path):
        try:
            if not os.path.isdir(path):
                self._logger.debug(f"Creating folder {path}")
                os.makedirs(path)
        except FileExistsError:
            pass

    def start_recording(self, frame, objects, resolution):
        self._logger.info("Starting recorder")
        self.is_recording = True
        self._segment_cleanup.pause()
        now = datetime.datetime.now()
        self.last_recording_start = now.isoformat()
        self.last_recording_end = None
        self._event_start = int(now.timestamp())

        if self.config.recorder.folder is None:
            self._logger.error("Output directory is not specified")
            return

        # Create filename
        now = datetime.datetime.now()
        video_name = f"{now.strftime('%H:%M:%S')}.{self.config.recorder.extension}"
        thumbnail_name = f"{now.strftime('%H:%M:%S')}.jpg"

        # Create foldername
        subfolder = self.subfolder_name(now)
        full_path = os.path.join(self.config.recorder.folder, subfolder)
        self.create_directory(full_path)

        if frame:
            self.create_thumbnail(
                os.path.join(full_path, thumbnail_name), frame, objects, resolution
            )

        self._recording_name = os.path.join(full_path, video_name)

    def concat_segments(self):
        self._segmenter.concat_segments(
            self._event_start - self.config.recorder.lookback,
            self._event_end,
            self._recording_name,
        )
        # Dont resume cleanup if new recording started during encoding
        if not self.is_recording:
            self._segment_cleanup.resume()

    def stop_recording(self):
        self._logger.info("Stopping recorder")
        self.is_recording = False
        now = datetime.datetime.now()
        self.last_recording_end = now.isoformat()
        self._event_end = int(now.timestamp())
        concat_thread = Thread(target=self.concat_segments)
        concat_thread.start()
