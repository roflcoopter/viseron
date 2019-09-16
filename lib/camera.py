# https://trac.ffmpeg.org/wiki/Concatenate
# https://unix.stackexchange.com/questions/233832/merge-two-video-clips-into-one-placing-them-next-to-each-other
import logging
import subprocess as sp
import threading
from queue import Full

import config
import cv2
import numpy as np
from retrying import retry

LOGGER = logging.getLogger(__name__)
#kernprof -v -l app.py
#python3 -m line_profiler app.py.lprof


class FFMPEGCamera(object):
    def __init__(self, frame_buffer, detection_lock, image_processing_buffer, decoded_frame_buffer):
        LOGGER.info('Initializing ffmpeg RTSP pipe')

        self.detector = None
        self.detection_lock = detection_lock
        self.image_processing_buffer = image_processing_buffer
        self.decoded_frame_buffer = decoded_frame_buffer

        # Activate OpenCL
        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(True)

        self.connected = False
        self.raw_image = None

        self.stream_width, self.stream_height, self.stream_fps, = \
            self.get_stream_characteristics(config.STREAM_URL)
        self.stream_fps = \
            config.STREAM_FPS if config.STREAM_FPS else self.stream_fps

        frame_buffer.maxsize = self.stream_fps * config.LOOKBACK_SECONDS

        LOGGER.info('Resolution = {}x{}'.format(self.stream_width,
                                                self.stream_height))
        LOGGER.info("FPS = {}".format(self.stream_fps))

    @staticmethod
    def get_stream_characteristics(stream_url):
        LOGGER.debug("Getting stream characteristics for {}".format(stream_url))
        stream = cv2.VideoCapture(stream_url)
        _, _ = stream.read()
        width = int(stream.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(stream.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(stream.get(cv2.CAP_PROP_FPS))
        stream.release()
        return width, height, fps

    def capture_pipe(self, frame_buffer, frame_ready):
        LOGGER.info('Starting capture process')

        ffmpeg_global_args = [
            '-hide_banner', '-loglevel', 'panic'
        ]

        ffmpeg_input_args = [
            '-avoid_negative_ts', 'make_zero',
            '-fflags', 'nobuffer',
            '-flags', 'low_delay',
            '-strict', 'experimental',
            '-fflags', '+genpts',
            '-rtsp_transport', 'tcp',
            '-stimeout', '5000000',
            '-use_wallclock_as_timestamps', '1'
        ]

        ffmpeg_input_hwaccel_args = [
            '-hwaccel', 'vaapi', '-vaapi_device', '/dev/dri/renderD128',
            '-threads', ' 8',
        ]

        ffmpeg_output_args = [
            '-an',
            '-f', 'rawvideo',
            '-pix_fmt', 'nv12',
            'pipe:1'
        ]

        ffmpeg_cmd = (['/root/bin/ffmpeg'] +
                      ffmpeg_global_args +
                      ffmpeg_input_args +
                      ffmpeg_input_hwaccel_args +
                      ['-rtsp_transport', 'tcp', '-i', config.STREAM_URL] +
                      ffmpeg_output_args
                     )
        LOGGER.debug("FFMPEG command: {}".format(" ".join(ffmpeg_cmd)))
        pipe = sp.Popen(ffmpeg_cmd, stdout=sp.PIPE, bufsize=10**8)

        self.connected = True

        bytes_to_read = int(self.stream_width*self.stream_height*1.5)

        while self.connected:
            self.raw_image = pipe.stdout.read(bytes_to_read)
            try:
                frame_buffer.put_nowait({
                    'frame': self.raw_image})
            except Full:
                frame_buffer.get()
                frame_buffer.put({
                    'frame': self.raw_image})

            with self.detection_lock:
                if self.detector.tracking:
                    try:
                        self.image_processing_buffer.put_nowait({
                            'frame': self.raw_image,
                            'trackable_objects': self.detector.filtered_objects
                        })
                    except Full:
                        LOGGER.error("Image processing queue full, discarding")
                        self.image_processing_buffer.get()
                        self.image_processing_buffer.put_nowait({
                            'frame': self.raw_image,
                            'trackable_objects': self.detector.filtered_objects
                        })
                    self.detector.filtered_objects = None
            frame_ready.set()
            frame_ready.clear()

        frame_ready.set()
        pipe.terminate()
        pipe.wait()
        LOGGER.info('FFMPEG frame grabber stopped')

    #@profile
    def decode_frame(self, frame=None):
        # Decode and returns the most recently read frame
        if not frame:
            frame = self.raw_image

        try:
            decoded_frame = (
                np
                .frombuffer(frame, np.uint8)
                .reshape(int(self.stream_height*1.5), self.stream_width)
            )
        except AttributeError:
            return False, None
        except IndexError:
            return False, None
        except ValueError:
            LOGGER.error("Unable to fetch frame. FFMPEG pipe seems broken")
            return False, None
        return True, cv2.UMat(decoded_frame)

    #@profile
    def current_frame(self):
        ret, frame = self.decode_frame()
        if ret:
            return True, cv2.cvtColor(frame, cv2.COLOR_YUV2RGB_NV21)
        return False, None

    def current_frame_resized(self, width, height):
        ret, frame = self.decode_frame()
        if ret:
            return True, cv2.resize(
                cv2.cvtColor(frame, cv2.COLOR_YUV2RGB_NV21),
                (width, height), interpolation=cv2.INTER_LINEAR)
        return False, None

    def decoder(self):
        LOGGER.info("Starting decoder thread")
        while self.detector.tracking:
            raw_image = self.image_processing_buffer.get()
            ret, frame = self.decode_frame(raw_image['frame'])
            if ret:
                self.decoded_frame_buffer.put({
                    'frame': cv2.resize(
                        cv2.cvtColor(frame, cv2.COLOR_YUV2RGB_NV21),
                        (config.OBJECT_TRACKING_WIDTH,
                         config.OBJECT_TRACKING_HEIGHT),
                        interpolation=cv2.INTER_LINEAR),
                    'trackable_objects': raw_image['trackable_objects']
                })
        LOGGER.info("Exiting decoder thread")
        return

    def release(self):
        self.connected = False
        return
