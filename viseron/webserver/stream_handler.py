"""Handles different kind of browser streams."""

import copy
import logging
from typing import Dict

import cv2
import imutils
import tornado.ioloop
import tornado.web
from tornado.queues import Queue

from viseron.config.config_camera import MJPEG_STREAM_SCHEMA
from viseron.const import TOPIC_FRAME_PROCESSED, TOPIC_STATIC_MJPEG_STREAMS
from viseron.data_stream import DataStream
from viseron.helpers import draw_contours, draw_mask, draw_objects, draw_zones
from viseron.nvr import FFMPEGNVR

LOGGER = logging.getLogger(__name__)


class StreamHandler(tornado.web.RequestHandler):
    """Represents a stream."""

    async def process_frame(self, nvr: FFMPEGNVR, frame, mjpeg_stream_config):
        """Return JPG with drawn objects, zones etc."""
        if mjpeg_stream_config["width"] and mjpeg_stream_config["height"]:
            resolution = mjpeg_stream_config["width"], mjpeg_stream_config["height"]
            frame.resize(
                "tornado", mjpeg_stream_config["width"], mjpeg_stream_config["height"]
            )
            processed_frame = frame.get_resized_frame("tornado").get()  # Convert to Mat
        else:
            resolution = nvr.camera.resolution
            processed_frame = frame.decoded_frame_mat_rgb

        if mjpeg_stream_config["draw_motion_mask"] and nvr.config.motion_detection.mask:
            draw_mask(
                processed_frame,
                nvr.config.motion_detection.mask,
            )

        if mjpeg_stream_config["draw_motion"] and frame.motion_contours:
            draw_contours(
                processed_frame,
                frame.motion_contours,
                resolution,
                nvr.config.motion_detection.area,
            )

        if mjpeg_stream_config["draw_zones"]:
            draw_zones(processed_frame, nvr.zones)

        if mjpeg_stream_config["draw_objects"]:
            draw_objects(
                processed_frame,
                frame.objects,
                resolution,
            )

        if mjpeg_stream_config["rotate"]:
            processed_frame = imutils.rotate_bound(
                processed_frame, mjpeg_stream_config["rotate"]
            )

        if mjpeg_stream_config["mirror"]:
            processed_frame = cv2.flip(processed_frame, 1)

        # Write a low quality image to save bandwidth
        ret, jpg = cv2.imencode(
            ".jpg", processed_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 100]
        )

        return ret, jpg


class DynamicStreamHandler(StreamHandler):
    """Represents a dynamic stream using query parameters."""

    async def get(self, camera):
        """Handle a GET request."""
        request_arguments = {k: self.get_argument(k) for k in self.request.arguments}
        LOGGER.debug(request_arguments)
        mjpeg_stream_config = MJPEG_STREAM_SCHEMA(request_arguments)
        LOGGER.debug(mjpeg_stream_config)
        nvr = FFMPEGNVR.nvr_list.get(camera, None)

        if not nvr:
            self.set_status(404)
            self.write(f"Camera {camera} not found.")
            self.finish()
            return

        self.set_header(
            "Content-Type", "multipart/x-mixed-replace;boundary=--jpgboundary"
        )
        self.set_header("Connection", "close")

        frame_queue = Queue(maxsize=10)
        frame_topic = f"{nvr.config.camera.name_slug}/{TOPIC_FRAME_PROCESSED}/*"
        unique_id = DataStream.subscribe_data(frame_topic, frame_queue)
        while True:
            try:
                item = await frame_queue.get()
                frame = copy.copy(item["frame"])
                ret, jpg = await self.process_frame(nvr, frame, mjpeg_stream_config)

                if ret:
                    self.write("--jpgboundary")
                    self.write("Content-type: image/jpeg\r\n")
                    self.write("Content-length: %s\r\n\r\n" % len(jpg))
                    self.write(jpg.tobytes())
                    await self.flush()
            except tornado.iostream.StreamClosedError:
                DataStream.unsubscribe_data(frame_topic, unique_id)
                LOGGER.debug(f"Stream closed for camera {nvr.config.camera.name_slug}")
                break


class StaticStreamHandler(StreamHandler):
    """Represents a static stream defined in config.yaml."""

    active_streams: Dict[str, object] = {}

    @tornado.gen.coroutine
    def stream(self, nvr, mjpeg_stream, mjpeg_stream_config, publish_frame_topic):
        """Subscribe to frames, draw on them, then publish processed frame."""
        frame_queue = Queue(maxsize=10)
        subscribe_frame_topic = (
            f"{nvr.config.camera.name_slug}/{TOPIC_FRAME_PROCESSED}/*"
        )
        unique_id = DataStream.subscribe_data(subscribe_frame_topic, frame_queue)

        while self.active_streams[mjpeg_stream]:
            item = yield frame_queue.get()
            frame = copy.copy(item["frame"])
            ret, jpg = yield self.process_frame(nvr, frame, mjpeg_stream_config)

            if ret:
                DataStream.publish_data(publish_frame_topic, jpg)

        DataStream.unsubscribe_data(subscribe_frame_topic, unique_id)
        LOGGER.debug(f"Closing stream {mjpeg_stream}")

    async def get(self, camera, mjpeg_stream):
        """Handle GET request."""
        nvr = FFMPEGNVR.nvr_list.get(camera, None)
        if not nvr:
            self.set_status(404)
            self.write(f"Camera {camera} not found.")
            self.finish()
            return

        mjpeg_stream_config = nvr.config.camera.static_mjpeg_streams.get(
            mjpeg_stream, None
        )
        if not mjpeg_stream_config:
            self.set_status(404)
            self.write(f"Stream {mjpeg_stream} not defined.")
            self.finish()
            return

        frame_queue = Queue(maxsize=10)
        frame_topic = (
            f"{TOPIC_STATIC_MJPEG_STREAMS}/{nvr.config.camera.name_slug}/{mjpeg_stream}"
        )
        unique_id = DataStream.subscribe_data(frame_topic, frame_queue)

        if self.active_streams.get(mjpeg_stream, False):
            self.active_streams[mjpeg_stream] += 1
            LOGGER.debug(
                "Stream {mjpeg_stream} already active, number of streams: "
                f"{self.active_streams[mjpeg_stream]}"
            )
        else:
            LOGGER.debug(f"Stream {mjpeg_stream} is not active, starting")
            self.active_streams[mjpeg_stream] = 1
            tornado.ioloop.IOLoop.current().spawn_callback(
                lambda: self.stream(
                    nvr, mjpeg_stream, mjpeg_stream_config, frame_topic
                ),
            )

        self.set_header(
            "Content-Type", "multipart/x-mixed-replace;boundary=--jpgboundary"
        )
        self.set_header("Connection", "close")
        while True:
            try:
                jpg = await frame_queue.get()
                self.write("--jpgboundary")
                self.write("Content-type: image/jpeg\r\n")
                self.write("Content-length: %s\r\n\r\n" % len(jpg))
                self.write(jpg.tobytes())
                await self.flush()
            except tornado.iostream.StreamClosedError:
                DataStream.unsubscribe_data(frame_topic, unique_id)
                LOGGER.debug(
                    f"Stream {mjpeg_stream} closed for camera "
                    f"{nvr.config.camera.name_slug}"
                )
                break
        self.active_streams[mjpeg_stream] -= 1
