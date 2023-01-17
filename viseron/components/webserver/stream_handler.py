"""Handles different kind of browser streams."""

import asyncio
import logging
from typing import Dict, Tuple

import cv2
import imutils
import tornado.ioloop
import tornado.web
from tornado.queues import Queue

from viseron.components.data_stream import DataStream
from viseron.components.nvr import COMPONENT as NVR_COMPONENT
from viseron.components.nvr.const import DATA_PROCESSED_FRAME_TOPIC
from viseron.components.nvr.nvr import NVR, DataProcessedFrame
from viseron.const import TOPIC_STATIC_MJPEG_STREAMS
from viseron.domains.camera import MJPEG_STREAM_SCHEMA
from viseron.domains.motion_detector import AbstractMotionDetectorScanner
from viseron.helpers import (
    draw_contours,
    draw_motion_mask,
    draw_object_mask,
    draw_objects,
    draw_zones,
)

from .request_handler import ViseronRequestHandler

LOGGER = logging.getLogger(__name__)


class StreamHandler(ViseronRequestHandler):
    """Represents a stream."""

    async def write_jpg(self, jpg):
        """Set the headers and write the jpg data."""
        self.write("--jpgboundary\r\n")
        self.write("Content-type: image/jpeg\r\n")
        self.write("Content-length: %s\r\n\r\n" % len(jpg))
        self.write(jpg.tobytes())
        await self.flush()

    @staticmethod
    async def process_frame(
        nvr: NVR, processed_frame: DataProcessedFrame, mjpeg_stream_config
    ):
        """Return JPG with drawn objects, zones etc."""
        _frame = processed_frame.frame.copy()

        if mjpeg_stream_config["width"] and mjpeg_stream_config["height"]:
            resolution = mjpeg_stream_config["width"], mjpeg_stream_config["height"]
            frame = cv2.resize(
                _frame,
                resolution,
                interpolation=cv2.INTER_LINEAR,
            )
        else:
            resolution = nvr.camera.resolution
            frame = _frame

        if nvr.motion_detector and isinstance(
            nvr.motion_detector, AbstractMotionDetectorScanner
        ):
            if mjpeg_stream_config["draw_motion_mask"] and nvr.motion_detector.mask:
                draw_motion_mask(
                    frame,
                    nvr.motion_detector.mask,
                )
            if mjpeg_stream_config["draw_motion"] and processed_frame.motion_contours:
                draw_contours(
                    frame,
                    processed_frame.motion_contours,
                    resolution,
                    nvr.motion_detector.area,
                )

        if nvr.object_detector:
            if mjpeg_stream_config["draw_zones"]:
                draw_zones(frame, nvr.object_detector.zones)

            if mjpeg_stream_config["draw_object_mask"] and nvr.object_detector.mask:
                draw_object_mask(
                    frame,
                    nvr.object_detector.mask,
                )
            if mjpeg_stream_config["draw_objects"] and processed_frame.objects_in_fov:
                draw_objects(
                    frame,
                    processed_frame.objects_in_fov,
                    resolution,
                )

        if mjpeg_stream_config["rotate"]:
            frame = imutils.rotate_bound(frame, mjpeg_stream_config["rotate"])

        if mjpeg_stream_config["mirror"]:
            frame = cv2.flip(frame, 1)

        # Write a low quality image to save bandwidth
        ret, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
        return ret, jpg


class DynamicStreamHandler(StreamHandler):
    """Represents a dynamic stream using query parameters."""

    async def get(self, camera):
        """Handle a GET request."""
        request_arguments = {k: self.get_argument(k) for k in self.request.arguments}
        mjpeg_stream_config = MJPEG_STREAM_SCHEMA(request_arguments)

        tries = 0
        while True:
            if tries == 60:
                self.set_status(404)
                self.write(f"Camera {camera} not found.")
                self.finish()
                return

            nvr_data = self._vis.data.get(NVR_COMPONENT, None)
            if not nvr_data:
                tries += 1
                await asyncio.sleep(1)
                continue

            nvr: NVR = self._vis.data[NVR_COMPONENT].get(camera, None)
            if not nvr:
                tries += 1
                await asyncio.sleep(1)
                continue
            break

        self.set_header(
            "Content-Type", "multipart/x-mixed-replace;boundary=--jpgboundary"
        )
        self.set_header("Connection", "close")

        frame_queue = Queue(maxsize=1)
        frame_topic = DATA_PROCESSED_FRAME_TOPIC.format(
            camera_identifier=nvr.camera.identifier
        )
        unique_id = DataStream.subscribe_data(
            frame_topic, frame_queue, ioloop=tornado.ioloop.IOLoop.current()
        )
        while True:
            try:
                processed_frame: DataProcessedFrame = await frame_queue.get()
                ret, jpg = await self.process_frame(
                    nvr, processed_frame, mjpeg_stream_config
                )

                if ret:
                    await self.write_jpg(jpg)
            except tornado.iostream.StreamClosedError:
                DataStream.unsubscribe_data(frame_topic, unique_id)
                LOGGER.debug(f"Stream closed for camera {nvr.camera.identifier}")
                break


class StaticStreamHandler(StreamHandler):
    """Represents a static stream defined in config.yaml."""

    active_streams: Dict[Tuple[str, str], object] = {}

    async def stream(self, nvr, mjpeg_stream, mjpeg_stream_config, publish_frame_topic):
        """Subscribe to frames, draw on them, then publish processed frame."""
        frame_queue = Queue(maxsize=1)
        frame_topic = DATA_PROCESSED_FRAME_TOPIC.format(
            camera_identifier=nvr.camera.identifier
        )
        unique_id = DataStream.subscribe_data(
            frame_topic, frame_queue, ioloop=tornado.ioloop.IOLoop.current()
        )

        while self.active_streams[(nvr.camera.identifier, mjpeg_stream)]:
            processed_frame: DataProcessedFrame = await frame_queue.get()
            ret, jpg = await self.process_frame(
                nvr, processed_frame, mjpeg_stream_config
            )

            if ret:
                DataStream.publish_data(publish_frame_topic, jpg)

        DataStream.unsubscribe_data(frame_topic, unique_id)
        LOGGER.debug(f"Closing stream {mjpeg_stream}")

    async def get(self, camera, mjpeg_stream):
        """Handle GET request."""
        tries = 0
        while True:
            if tries == 60:
                self.set_status(404)
                self.write(f"Camera {camera} not found.")
                self.finish()
                return

            nvr_data = self._vis.data.get(NVR_COMPONENT, None)
            if not nvr_data:
                tries += 1
                await asyncio.sleep(1)
                continue

            nvr: NVR = self._vis.data[NVR_COMPONENT].get(camera, None)
            if not nvr:
                tries += 1
                await asyncio.sleep(1)
                continue
            break

        mjpeg_stream_config = nvr.camera.mjpeg_streams.get(mjpeg_stream, None)
        if not mjpeg_stream_config:
            self.set_status(404)
            self.write(f"Stream {mjpeg_stream} not defined.")
            self.finish()
            return

        frame_queue = Queue(maxsize=1)
        frame_topic = (
            f"{TOPIC_STATIC_MJPEG_STREAMS}/{nvr.camera.identifier}/{mjpeg_stream}"
        )
        unique_id = DataStream.subscribe_data(
            frame_topic, frame_queue, ioloop=tornado.ioloop.IOLoop.current()
        )

        if self.active_streams.get((nvr.camera.identifier, mjpeg_stream), False):
            self.active_streams[(nvr.camera.identifier, mjpeg_stream)] += 1
            LOGGER.debug(
                f"Stream {mjpeg_stream} already active, number of streams: "
                f"{self.active_streams[(nvr.camera.identifier,mjpeg_stream)]}"
            )
        else:
            LOGGER.debug(f"Stream {mjpeg_stream} is not active, starting")
            self.active_streams[(nvr.camera.identifier, mjpeg_stream)] = 1
            tornado.ioloop.IOLoop.current().spawn_callback(
                self.stream, nvr, mjpeg_stream, mjpeg_stream_config, frame_topic
            )

        self.set_header(
            "Content-Type", "multipart/x-mixed-replace;boundary=--jpgboundary"
        )
        self.set_header("Connection", "close")
        while True:
            try:
                jpg = await frame_queue.get()
                await self.write_jpg(jpg)
            except tornado.iostream.StreamClosedError:
                DataStream.unsubscribe_data(frame_topic, unique_id)
                LOGGER.debug(
                    f"Stream {mjpeg_stream} closed for camera "
                    f"{nvr.camera.identifier}"
                )
                break
        self.active_streams[(nvr.camera.identifier, mjpeg_stream)] -= 1
