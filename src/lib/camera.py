import json
import logging
import os
import subprocess as sp
from threading import Event
from time import sleep

import cv2
import numpy as np

from const import CAMERA_SEGMENT_ARGS
from lib.helpers import pop_if_full

LOGGER = logging.getLogger(__name__)


class Frame:
    def __init__(self, raw_frame, frame_width, frame_height):
        self._raw_frame = raw_frame
        self._frame_width = frame_width
        self._frame_height = frame_height
        self._decoded_frame = None
        self._decoded_frame_umat = None
        self._decoded_frame_umat_rgb = None
        self._decoded_frame_mat_rgb = None
        self._resized_frames = {}
        self._objects = []
        self._motion_contours = None

    def decode_frame(self):
        try:
            self._decoded_frame = np.frombuffer(self.raw_frame, np.uint8).reshape(
                int(self.frame_height * 1.5), self.frame_width
            )
        # except AttributeError:
        # return False
        # except IndexError:
        # return False
        except ValueError:
            return False
        return True

    def resize(self, decoder_name, width, height):
        self._resized_frames[decoder_name] = cv2.resize(
            self.decoded_frame_umat_rgb,
            (width, height),
            interpolation=cv2.INTER_LINEAR,
        )

    def get_resized_frame(self, decoder_name):
        return self._resized_frames.get(decoder_name)

    @property
    def raw_frame(self):
        return self._raw_frame

    @property
    def frame_width(self):
        return self._frame_width

    @property
    def frame_height(self):
        return self._frame_height

    @property
    def decoded_frame(self):
        if self._decoded_frame is None:
            self._decoded_frame = self.decode_frame()
        return self._decoded_frame

    @property
    def decoded_frame_umat(self):
        if self._decoded_frame_umat is None:
            self._decoded_frame_umat = cv2.UMat(self.decoded_frame)
        return self._decoded_frame_umat

    @property
    def decoded_frame_umat_rgb(self):
        if self._decoded_frame_umat_rgb is None:
            self._decoded_frame_umat_rgb = cv2.cvtColor(
                self.decoded_frame_umat, cv2.COLOR_YUV2RGB_NV21
            )
        return self._decoded_frame_umat_rgb

    @property
    def decoded_frame_mat_rgb(self):
        if self._decoded_frame_mat_rgb is None:
            self._decoded_frame_mat_rgb = self.decoded_frame_umat_rgb.get()
        return self._decoded_frame_mat_rgb

    @property
    def objects(self):
        return self._objects

    @objects.setter
    def objects(self, objects):
        self._objects = objects

    @property
    def motion_contours(self):
        return self._motion_contours

    @motion_contours.setter
    def motion_contours(self, motion_contours):
        self._motion_contours = motion_contours


class FFMPEGCamera:
    def __init__(self, config, frame_buffer):
        self._logger = logging.getLogger(__name__ + "." + config.camera.name_slug)
        self._config = config
        self._frame_buffer = frame_buffer
        self._connected = False
        self._connection_error = False
        self.stream_width = None
        self.stream_height = None
        self.stream_fps = None
        self.resolution = None
        self.frame_ready = Event()
        self.scan_for_objects = Event()  # Set when frame should be scanned
        self.scan_for_motion = Event()  # Set when frame should be scanned

        # Activate OpenCL
        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(True)

        self.initialize_camera()

    def initialize_camera(self):
        self._logger = logging.getLogger(__name__ + "." + self._config.camera.name_slug)
        if getattr(self._config.camera.logging, "level", None):
            self._logger.setLevel(self._config.camera.logging.level)

        self._logger.debug(f"Initializing camera {self._config.camera.name}")

        if (
            not self._config.camera.width
            or not self._config.camera.height
            or not self._config.camera.fps
        ):
            (
                stream_width,
                stream_height,
                stream_fps,
                stream_codec,
            ) = self.get_stream_information(self._config.camera.stream_url)

        self.stream_width = (
            self._config.camera.width if self._config.camera.width else stream_width
        )
        self.stream_height = (
            self._config.camera.height if self._config.camera.height else stream_height
        )
        self.stream_fps = (
            self._config.camera.fps if self._config.camera.fps else stream_fps
        )
        self.stream_codec = stream_codec

        self.resolution = self.stream_width, self.stream_height
        frame_buffer_size = self.stream_fps * self._config.recorder.lookback
        if frame_buffer_size > 0:
            self._frame_buffer.maxsize = frame_buffer_size

        self._logger.debug(
            f"Resolution: {self.stream_width}x{self.stream_height} "
            f"@ {self.stream_fps} FPS"
        )
        self._logger.debug(f"FFMPEG decoder command: {' '.join(self.build_command())}")
        self._logger.debug(f"Camera {self._config.camera.name} initialized")

    @staticmethod
    def ffprobe_stream_information(stream_url):
        width, height, fps, codec = 0, 0, 0, None
        ffprobe_command = [
            "ffprobe",
            "-hide_banner",
            "-loglevel",
            "quiet",
            "-print_format",
            "json",
            "-show_error",
            "-show_streams",
            "-select_streams",
            "v",
        ] + [stream_url]

        pipe = sp.Popen(ffprobe_command, stdout=sp.PIPE, stderr=sp.STDOUT)
        output, _ = pipe.communicate()
        pipe.wait()

        stream_information = json.loads(output)["streams"][0]
        numerator = int(stream_information["avg_frame_rate"].split("/")[0])
        denominator = int(stream_information["avg_frame_rate"].split("/")[1])

        try:
            fps = numerator / denominator
        except ZeroDivisionError:
            pass

        width = stream_information.get("width", 0)
        height = stream_information.get("height", 0)
        codec = stream_information.get("codec_name", None)

        return (
            width,
            height,
            fps,
            codec,
        )

    @staticmethod
    def opencv_stream_information(stream_url):
        width, height, fps = 0, 0, 0
        stream = cv2.VideoCapture(stream_url)
        _, _ = stream.read()
        width = int(stream.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(stream.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(stream.get(cv2.CAP_PROP_FPS))
        stream.release()
        return width, height, fps

    def get_stream_information(self, stream_url):
        self._logger.debug("Getting stream information for {}".format(stream_url))
        width, height, fps, codec = self.ffprobe_stream_information(stream_url)

        if width == 0 or height == 0 or fps == 0:
            self._logger.warning(
                "ffprobe failed to get stream information. Using OpenCV instead"
            )
            width, height, fps = self.opencv_stream_information(stream_url)

        return width, height, fps, codec

    def get_codec(self):
        if self._config.camera.codec:
            return self._config.camera.codec

        if self.stream_codec:
            codec = self._config.camera.codec_map.get(self.stream_codec, None)
            if codec:
                return ["-c:v", codec]

        return []

    def build_command(self, ffmpeg_loglevel=None, single_frame=False):
        camera_segment_args = []
        if not single_frame:
            camera_segment_args = CAMERA_SEGMENT_ARGS + [
                os.path.join(
                    self._config.recorder.segments_folder,
                    self._config.camera.name,
                    "%Y%m%d%H%M%S.mp4",
                )
            ]

        return (
            ["ffmpeg"]
            + self._config.camera.global_args
            + ["-loglevel"]
            + (
                [ffmpeg_loglevel]
                if ffmpeg_loglevel
                else [self._config.camera.ffmpeg_loglevel]
            )
            + self._config.camera.input_args
            + self._config.camera.hwaccel_args
            + self.get_codec()
            + (
                ["-rtsp_transport", self._config.camera.rtsp_transport]
                if self._config.camera.stream_format == "rtsp"
                else []
            )
            + ["-i", self._config.camera.stream_url]
            + camera_segment_args
            + (["-frames:v", "1"] if single_frame else [])
            + self._config.camera.output_args
        )

    def pipe(self, stderr=False, single_frame=False):
        if stderr:
            return sp.Popen(
                self.build_command(ffmpeg_loglevel="fatal", single_frame=single_frame),
                stdout=sp.PIPE,
                stderr=sp.PIPE,
                bufsize=10 ** 8,
            )
        return sp.Popen(self.build_command(), stdout=sp.PIPE, bufsize=10 ** 8,)

    def capture_pipe(
        self,
        object_decoder_interval,
        object_decoder_queue,
        object_return_queue,
        motion_decoder_interval,
        motion_decoder_queue,
        motion_return_queue,
    ):
        self._logger.debug("Starting capture thread")
        self._connected = True
        # First read a single frame to make sure the ffmpeg command is correct
        bytes_to_read = int(self.stream_width * self.stream_height * 1.5)
        retry = False
        self._logger.debug("Performing a sanity check on the ffmpeg command")
        while True:
            pipe = self.pipe(stderr=True, single_frame=True)
            _, stderr = pipe.communicate()
            if stderr and not any(
                err in stderr.decode()
                for err in self._config.camera.ffmpeg_recoverable_errors
            ):
                self._logger.error(
                    f"Error starting decoder pipe! {stderr.decode()} "
                    f"Retrying in 5 seconds"
                )
                sleep(5)
                retry = True
                continue
            if retry:
                self._logger.error("Succesful reconnection!")
            break

        pipe = self.pipe()

        object_frame_number = 0
        object_first_scan = False
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

        while self._connected:
            if self._connection_error:
                sleep(5)
                self._logger.error("Restarting frame pipe")
                pipe.terminate()
                pipe.communicate()
                pipe = self.pipe()
                self._connection_error = False
                self._logger.error("Successful reconnection!")

            current_frame = Frame(
                pipe.stdout.read(bytes_to_read), self.stream_width, self.stream_height
            )
            pop_if_full(self._frame_buffer, current_frame)

            if self.scan_for_objects.is_set():
                if object_frame_number % object_decoder_interval_calculated == 0:
                    if object_first_scan:
                        # force motion detection on same frame to save computing power
                        motion_frame_number = 0
                        object_first_scan = False
                    object_frame_number = 0
                    pop_if_full(
                        object_decoder_queue,
                        {
                            "decoder_name": "object_detection",
                            "frame": current_frame,
                            "object_return_queue": object_return_queue,
                            "camera_config": self._config,
                        },
                        logger=self._logger,
                        name="object_decoder_queue",
                        warn=True,
                    )

                object_frame_number += 1
            else:
                object_frame_number = 0
                object_first_scan = True

            if self.scan_for_motion.is_set():
                if motion_frame_number % motion_decoder_interval_calculated == 0:
                    motion_frame_number = 0
                    pop_if_full(
                        motion_decoder_queue,
                        {
                            "decoder_name": "motion_detection",
                            "frame": current_frame,
                            "motion_return_queue": motion_return_queue,
                        },
                        logger=self._logger,
                        name="motion_decoder_queue",
                        warn=True,
                    )

                motion_frame_number += 1
            else:
                motion_frame_number = 0

            self.frame_ready.set()
            self.frame_ready.clear()

        pipe.terminate()
        pipe.communicate()
        self._logger.info("FFMPEG frame grabber stopped")

    def decoder(self, input_queue, output_queue, width, height):
        """Decodes the frame, leaves any other potential keys in the dict untouched"""
        self._logger.debug("Starting decoder thread")
        while True:
            input_item = input_queue.get()
            if input_item["frame"].decode_frame():
                input_item["frame"].resize(input_item["decoder_name"], width, height)
                pop_if_full(
                    output_queue,
                    input_item,
                    logger=self._logger,
                    name=f"{input_item['decoder_name']} input",
                    warn=True,
                )
                continue

            self._logger.error("Unable to decode frame. FFMPEG pipe seems broken")
            self._connection_error = True

        self._logger.debug("Exiting decoder thread")

    def release(self):
        self._connected = False
