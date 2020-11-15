import time

import tornado.web
import tornado.ioloop
from lib.nvr import FFMPEGNVR


class StreamHandler(tornado.web.RequestHandler):
    async def get(self, camera):
        nvr = FFMPEGNVR.nvr_list.get(camera, None)

        if not nvr:
            self.set_status(404)
            self.write(f"Camera {camera} not found.")
            self.finish()
            return

        ioloop = tornado.ioloop.IOLoop.current()
        self.set_header(
            "Content-Type", "multipart/x-mixed-replace;boundary=--jpgboundary"
        )
        self.set_header("Connection", "close")

        my_boundary = "--jpgboundary"
        while True:
            try:
                img = FFMPEGNVR.nvr_list[camera]._mqtt.published_frame
                self.write(my_boundary)
                self.write("Content-type: image/jpeg\r\n")
                self.write("Content-length: %s\r\n\r\n" % len(img))
                self.write(img.tobytes())
                await self.flush()
                await ioloop.current().run_in_executor(None, time.sleep, 1)
            except tornado.iostream.StreamClosedError:
                print("Stream Closed")
                break
