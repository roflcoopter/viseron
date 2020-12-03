import copy

import cv2
import tornado.ioloop
import tornado.web
from const import TOPIC_FRAME_PROCESSED
from lib.data_stream import DataStream
from lib.helpers import draw_mask
from lib.nvr import FFMPEGNVR
from tornado.queues import Queue


class StreamHandler(tornado.web.RequestHandler):
    async def process_frame(
        self, config, frame, width, height, draw_motion, draw_motion_mask
    ):
        if width and height:
            frame.resize("tornado", int(width), int(height))
            processed_frame = frame.get_resized_frame("tornado").get()  # Convert to Mat
        else:
            processed_frame = frame.decoded_frame_mat_rgb

        if draw_motion_mask:
            draw_mask(
                processed_frame, config.motion_detection.mask,
            )

        return processed_frame

    async def get(self, camera):
        nvr = FFMPEGNVR.nvr_list.get(camera, None)

        if not nvr:
            self.set_status(404)
            self.write(f"Camera {camera} not found.")
            self.finish()
            return

        width = self.get_query_argument("width", None)
        height = self.get_query_argument("height", None)
        draw_motion = self.get_query_argument("draw_motion", False)
        draw_motion_mask = self.get_query_argument("draw_motion_mask", False)

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
                frame = copy.copy(item)
                processed_frame = await self.process_frame(
                    nvr.config, frame, width, height, draw_motion, draw_motion_mask
                )

                ret, jpg = cv2.imencode(
                    ".jpg", processed_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 100],
                )
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
