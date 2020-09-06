# https://trac.ffmpeg.org/wiki/Concatenate
# https://unix.stackexchange.com/questions/233832/merge-two-video-clips-into-one-placing-them-next-to-each-other
import logging
import subprocess as sp
from time import sleep

import cv2
import numpy as np
from lib.helpers import pop_if_full
from const import FFMPEG_ERROR_WHILE_DECODING


class FFMPEGCamera:
    def __init__(self, config, frame_buffer):
        self._logger = logging.getLogger(__name__ + "." + config.camera.name_slug)
        self._logger.debug("Initializing ffmpeg RTSP pipe")
        self.config = config

        # Activate OpenCL
        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(True)

        self.connected = False
        self.connection_error = False
        self.raw_image = None
        self.current_frame = None

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
            (
                self.stream_width,
                self.stream_height,
                self.stream_fps,
            ) = self.get_stream_characteristics(self.config.camera.stream_url)

        self.resolution = self.stream_width, self.stream_height
        frame_buffer.maxsize = self.stream_fps * self.config.recorder.lookback

        self._logger.info(
            f"Resolution: {self.stream_width}x{self.stream_height} "
            f"@ {self.stream_fps} FPS"
        )
        self._logger.debug(f"FFMPEG decoder command: {' '.join(self.build_command())}")

    def get_stream_characteristics(self, stream_url):
        self._logger.debug("Getting stream characteristics for {}".format(stream_url))
        stream = cv2.VideoCapture(stream_url)
        _, _ = stream.read()
        width = int(stream.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(stream.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(stream.get(cv2.CAP_PROP_FPS))
        stream.release()
        return width, height, fps

    def build_command(self, ffmpeg_loglevel="panic", single_frame=False):
        return (
            ["ffmpeg"]
            + self.config.camera.global_args
            + ["-loglevel", ffmpeg_loglevel]
            + self.config.camera.input_args
            + self.config.camera.hwaccel_args
            + self.config.camera.codec
            + (
                ["-rtsp_transport", "tcp"]
                if self.config.camera.stream_format == "rtsp"
                else []
            )
            + ["-i", self.config.camera.stream_url]
            + self.config.camera.filter_args
            + (["-frames:v", "1"] if single_frame else [])
            + self.config.camera.output_args
        )

    def pipe(self, stderr=False, single_frame=False):
        if stderr:
            return sp.Popen(
                self.build_command(ffmpeg_loglevel="error", single_frame=single_frame),
                stdout=sp.PIPE,
                stderr=sp.PIPE,
                bufsize=10 ** 8,
            )
        return sp.Popen(
            self.build_command(single_frame=False), stdout=sp.PIPE, bufsize=10 ** 8,
        )

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
        self._logger.debug("Starting capture process")
        # First read a single frame to make sure the ffmpeg command is correct
        bytes_to_read = int(self.stream_width * self.stream_height * 1.5)
        pipe = self.pipe(stderr=True, single_frame=True)
        _, stderr = pipe.communicate()
        if stderr and FFMPEG_ERROR_WHILE_DECODING not in stderr.decode():
            self._logger.error(f"Error starting decoder pipe! {stderr.decode()}")
            return

        pipe = self.pipe()
        self.connected = True

        object_frame_number = 0
        object_decoder_interval_calculated = round(
            object_decoder_interval * self.stream_fps
        )
        self._logger.debug(
            f"Running object detection at {object_decoder_interval}s interval, "
            f"every {object_decoder_interval_calculated} frame(s)"
        )

        motion_frame_number = 0
        motion_decoder_interval_calculated = round(
            motion_decoder_interval * self.stream_fps
        )
        self._logger.debug(
            f"Running motion detection at {motion_decoder_interval}s interval, "
            f"every {motion_decoder_interval_calculated} frame(s)"
        )

        while self.connected:
            if self.connection_error:
                sleep(5)
                self._logger.error("Restarting frame pipe")
                pipe.terminate()
                pipe.communicate()
                pipe = self.pipe()
                self.connection_error = False

            self.raw_image = pipe.stdout.read(bytes_to_read)
            pop_if_full(frame_buffer, {"frame": self.raw_image})

            if scan_for_objects.is_set():
                if object_frame_number % object_decoder_interval_calculated == 0:
                    object_frame_number = 0
                    pop_if_full(
                        object_decoder_queue,
                        {
                            "raw_frame": self.raw_image,
                            "object_event": object_event,
                            "object_return_queue": object_return_queue,
                            "camera_config": self.config,
                        },
                    )

                object_frame_number += 1
            else:
                object_frame_number = 0

            if scan_for_motion.is_set():
                if motion_frame_number % motion_decoder_interval_calculated == 0:
                    motion_frame_number = 0
                    pop_if_full(motion_decoder_queue, {"raw_frame": self.raw_image})

                motion_frame_number += 1
            else:
                motion_frame_number = 0

            frame_ready.set()
            frame_ready.clear()

        frame_ready.set()
        pipe.terminate()
        pipe.communicate()
        self._logger.info("FFMPEG frame grabber stopped")

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
            self._logger.error("Unable to fetch frame. FFMPEG pipe seems broken")
            self.connection_error = True
            return False, None
        return True, cv2.UMat(decoded_frame)

    def decoder(self, input_queue, output_queue, width, height):
        """Decodes the frame, leaves any other potential keys in the dict untouched"""
        self._logger.debug("Starting decoder thread")
        while True:
            input_item = input_queue.get()
            ret, frame = self.decode_frame(input_item["raw_frame"])
            if ret:
                self.current_frame = cv2.cvtColor(frame, cv2.COLOR_YUV2RGB_NV21)
                input_item["full_frame"] = self.current_frame
                input_item["frame"] = cv2.resize(
                    self.current_frame, (width, height), interpolation=cv2.INTER_LINEAR,
                )
                pop_if_full(output_queue, input_item)

        self._logger.debug("Exiting decoder thread")

    def release(self):
        self.connected = False
