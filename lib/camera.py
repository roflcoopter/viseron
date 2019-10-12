# https://trac.ffmpeg.org/wiki/Concatenate
# https://unix.stackexchange.com/questions/233832/merge-two-video-clips-into-one-placing-them-next-to-each-other
import logging
import subprocess as sp

import cv2
import numpy as np
from lib.helpers import pop_if_full

LOGGER = logging.getLogger(__name__)
# kernprof -v -l app.py
# python3 -m line_profiler app.py.lprof


class FFMPEGCamera(object):
    def __init__(self, config, frame_buffer):
        LOGGER.info("Initializing ffmpeg RTSP pipe")
        self.config = config

        # Activate OpenCL
        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(True)

        self.connected = False
        self.connection_error = True
        self.raw_image = None

        if (
            self.config.camera.width
            and self.config.camera.height
            and self.config.camera.fps
        ):
            self.stream_width, self.stream_height, self.stream_fps = (
                self.config.camera.width,
                self.config.camera.height,
                self.config.camera.fps,
            )
        else:
            self.stream_width, self.stream_height, self.stream_fps = self.get_stream_characteristics(
                self.config.stream_url
            )

        self.resolution = self.stream_width, self.stream_height
        frame_buffer.maxsize = self.stream_fps * self.config.recorder.lookback

        LOGGER.info(
            f"Resolution = {self.stream_width}x{self.stream_height} @ {self.stream_fps} FPS"
        )

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

    def capture_pipe(
        self,
        frame_buffer,
        frame_ready,
        object_decoder_interval,
        object_decoder_queue,
        scan_for_objects,
        object_event,
        object_return_queue,
        motion_decoder_interval,
        motion_decoder_queue,
        scan_for_motion,
    ):
        LOGGER.info("Starting capture process")

        ffmpeg_global_args = ["-hide_banner", "-loglevel", "panic"]

        ffmpeg_input_args = [
            "-avoid_negative_ts",
            "make_zero",
            "-fflags",
            "nobuffer",
            "-flags",
            "low_delay",
            "-strict",
            "experimental",
            "-fflags",
            "+genpts",
            "-rtsp_transport",
            "tcp",
            "-stimeout",
            "5000000",
            "-use_wallclock_as_timestamps",
            "1",
        ]

        ffmpeg_input_hwaccel_args = [
            "-hwaccel",
            "vaapi",
            "-vaapi_device",
            "/dev/dri/renderD128",
            "-threads",
            " 8",
        ]

        ffmpeg_output_args = ["-an", "-f", "rawvideo", "-pix_fmt", "nv12", "pipe:1"]

        ffmpeg_cmd = (
            ["/root/bin/ffmpeg"]
            + ffmpeg_global_args
            + ffmpeg_input_args
            + ffmpeg_input_hwaccel_args
            + ["-rtsp_transport", "tcp", "-i", self.config.camera.stream_url]
            + ffmpeg_output_args
        )
        LOGGER.debug("FFMPEG command: {}".format(" ".join(ffmpeg_cmd)))
        pipe = sp.Popen(ffmpeg_cmd, stdout=sp.PIPE, bufsize=10 ** 8)

        self.connected = True
        object_frame_number = 0
        motion_frame_number = 0

        bytes_to_read = int(self.stream_width * self.stream_height * 1.5)

        while self.connected:
            self.raw_image = pipe.stdout.read(bytes_to_read)
            pop_if_full(frame_buffer, {"frame": self.raw_image})

            if scan_for_objects.is_set():
                if object_frame_number % object_decoder_interval == 0:
                    object_frame_number = 0
                    pop_if_full(
                        object_decoder_queue,
                        {
                            "frame": self.raw_image,
                            "object_event": object_event,
                            "object_return_queue": object_return_queue,
                        },
                    )

                object_frame_number += 1
            else:
                object_frame_number = 0

            if scan_for_motion.is_set():
                if motion_frame_number % motion_decoder_interval == 0:
                    motion_frame_number = 0
                    pop_if_full(motion_decoder_queue, {"frame": self.raw_image})

                motion_frame_number += 1
            else:
                motion_frame_number = 0

            frame_ready.set()
            frame_ready.clear()

        frame_ready.set()
        pipe.terminate()
        pipe.communicate()
        LOGGER.info("FFMPEG frame grabber stopped")

    # @profile
    def decode_frame(self, frame=None):
        # Decode and returns the most recently read frame
        if not frame:
            frame = self.raw_image

        try:
            decoded_frame = np.frombuffer(frame, np.uint8).reshape(
                int(self.stream_height * 1.5), self.stream_width
            )
        except AttributeError:
            return False, None
        except IndexError:
            return False, None
        except ValueError:
            LOGGER.error("Unable to fetch frame. FFMPEG pipe seems broken")
            self.connection_error = True
            return False, None
        return True, cv2.UMat(decoded_frame)

    def decoder(self, input_queue, output_queue, width, height):
        """Decodes the frame, leaves any other potential keys in the dict untouched"""
        LOGGER.info("Starting decoder thread")
        while True:
            input_item = input_queue.get()
            ret, frame = self.decode_frame(input_item["frame"])
            if ret:
                input_item["frame"] = cv2.resize(
                    cv2.cvtColor(frame, cv2.COLOR_YUV2RGB_NV21),
                    (width, height),
                    interpolation=cv2.INTER_LINEAR,
                )
                pop_if_full(output_queue, input_item)

        LOGGER.info("Exiting decoder thread")

    def release(self):
        self.connected = False
