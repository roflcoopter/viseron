import copy

import cv2
import tornado.ioloop
import tornado.web
from const import TOPIC_FRAME_PROCESSED
from lib.data_stream import DataStream
from lib.helpers import draw_contours, draw_mask, draw_objects, draw_zones
from lib.nvr import FFMPEGNVR
from tornado.queues import Queue


class StreamHandler(tornado.web.RequestHandler):
    async def process_frame(self, nvr: FFMPEGNVR, frame, width, height, draw):
        if width and height:
            resolution = (int(width), int(height))
            frame.resize("tornado", int(width), int(height))
            processed_frame = frame.get_resized_frame("tornado").get()  # Convert to Mat
        else:
            resolution = nvr.camera.resolution
            processed_frame = frame.decoded_frame_mat_rgb

        if draw.get("draw_motion_mask", False) and nvr.config.motion_detection.mask:
            draw_mask(
                processed_frame, nvr.config.motion_detection.mask,
            )

        if draw.get("draw_motion", False) and frame.motion_contours:
            draw_contours(
                processed_frame,
                frame.motion_contours,
                resolution,
                nvr.config.motion_detection.area,
            )

        if draw.get("draw_zones", False):
            draw_zones(processed_frame, nvr.zones)

        if draw.get("draw_objects", False):
            draw_objects(
                processed_frame, frame.objects, resolution,
            )

        # Write a low quality image to save bandwidth
        ret, jpg = cv2.imencode(
            ".jpg", processed_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 100]
        )

        return ret, jpg

    async def get(self, camera):
        nvr = FFMPEGNVR.nvr_list.get(camera, None)

        if not nvr:
            self.set_status(404)
            self.write(f"Camera {camera} not found.")
            self.finish()
            return

        width = self.get_query_argument("width", None)
        height = self.get_query_argument("height", None)
        draw = {}
        draw["draw_objects"] = self.get_query_argument("draw_objects", False)
        draw["draw_motion"] = self.get_query_argument("draw_motion", False)
        draw["draw_motion_mask"] = self.get_query_argument("draw_motion_mask", False)
        draw["draw_zones"] = self.get_query_argument("draw_zones", False)

        self.set_header(
            "Content-Type", "multipart/x-mixed-replace;boundary=--jpgboundary"
        )
        self.set_header("Connection", "close")

        my_boundary = "--jpgboundary"
        frame_queue = Queue(maxsize=10)
        frame_topic = f"{nvr.config.camera.name_slug}/{TOPIC_FRAME_PROCESSED}/*"
        unique_id = DataStream.subscribe_data(frame_topic, frame_queue)
        while True:
            try:
                item = await frame_queue.get()
                frame = copy.copy(item["frame"])
                ret, jpg = await self.process_frame(nvr, frame, width, height, draw)

                if ret:
                    self.write(my_boundary)
                    self.write("Content-type: image/jpeg\r\n")
                    self.write("Content-length: %s\r\n\r\n" % len(jpg))
                    self.write(jpg.tobytes())
                    await self.flush()
            except tornado.iostream.StreamClosedError:
                DataStream.unsubscribe_data(frame_topic, unique_id)
                print("Stream Closed")
                break
