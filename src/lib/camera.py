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
from viseron_exceptions import FFprobeError

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


class Stream:
    def __init__(
        self, logger, config, stream_config, write_segments=True, pipe_frames=True,
    ):
        self._logger = logger
        self._config = config
        self.stream_config = stream_config
        self._write_segments = write_segments
        self._pipe_frames = pipe_frames

        self._pipe = None

        stream_codec = None
        if (
            not self.stream_config.width
            or not self.stream_config.height
            or not self.stream_config.fps
            or not self.stream_config.codec
        ):
            (width, height, fps, stream_codec,) = self.get_stream_information(
                self.stream_config.stream_url
            )

        self.width = self.stream_config.width if self.stream_config.width else width
        self.height = self.stream_config.height if self.stream_config.height else height
        self.fps = self.stream_config.fps if self.stream_config.fps else fps
        self.stream_codec = stream_codec

        self._frame_bytes = int(self.width * self.height * 1.5)

    def ffprobe_stream_information(self, stream_url):
        width, height, fps, codec = 0, 0, 0, None
        ffprobe_command = [
            "ffprobe",
            "-hide_banner",
            "-loglevel",
            "fatal",
            "-print_format",
            "json",
            "-show_error",
            "-show_streams",
            "-select_streams",
            "v",
        ] + [stream_url]

        pipe = sp.Popen(ffprobe_command, stdout=sp.PIPE)
        stdout, _ = pipe.communicate()
        pipe.wait()
        output = json.loads(stdout)

        if output.get("error", None):
            self._logger.error(
                f"Failed to connect to stream: "
                f"{output['error'].get('string', 'Unknown error')}"
            )
            raise FFprobeError

        try:
            stream_information = output["streams"][0]
            numerator = int(stream_information.get("avg_frame_rate", 0).split("/")[0])
            denominator = int(stream_information.get("avg_frame_rate", 0).split("/")[1])
        except KeyError:
            return (
                width,
                height,
                fps,
                codec,
            )

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

    def get_stream_information(self, stream_url):
        self._logger.debug("Getting stream information for {}".format(stream_url))
        width, height, fps, codec = self.ffprobe_stream_information(stream_url)

        if width == 0 or height == 0 or fps == 0:
            self._logger.warning("ffprobe failed to get stream information")

        return width, height, fps, codec

    def get_codec(self, stream_config, stream_codec):
        if stream_config.codec:
            return stream_config.codec

        if stream_codec:
            codec = stream_config.codec_map.get(stream_codec, None)
            if codec:
                return ["-c:v", codec]

        return []

    def stream_command(self, stream_config, stream_codec):
        return (
            stream_config.input_args
            + stream_config.hwaccel_args
            + self.get_codec(stream_config, stream_codec)
            + (
                ["-rtsp_transport", stream_config.rtsp_transport]
                if stream_config.stream_format == "rtsp"
                else []
            )
            + ["-i", stream_config.stream_url]
        )

    def build_command(self, ffmpeg_loglevel=None, single_frame=False):
        camera_segment_args = []
        if not single_frame and self._write_segments:
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
            + self.stream_command(self.stream_config, self.stream_codec)
            + (["-frames:v", "1"] if single_frame else [])
            + camera_segment_args
            + (self._config.camera.output_args if self._pipe_frames else [])
        )

    def pipe(self, stderr=False, single_frame=False):
        if stderr:
            return sp.Popen(
                self.build_command(ffmpeg_loglevel="fatal", single_frame=single_frame),
                stdout=sp.PIPE,
                stderr=sp.PIPE,
            )
        if self._pipe_frames:
            return sp.Popen(self.build_command(), stdout=sp.PIPE)
        return sp.Popen(self.build_command())

    def check_command(self):
        self._logger.debug("Performing a sanity check on the ffmpeg command")
        retry = False
        while True:
            pipe = self.pipe(stderr=True, single_frame=True)
            _, stderr = pipe.communicate()
            if stderr and not any(
                err in stderr.decode()
                for err in self._config.camera.ffmpeg_recoverable_errors
            ):
                self._logger.error(
                    f"Error starting decoder command! {stderr.decode()} "
                    f"Retrying in 5 seconds"
                )
                sleep(5)
                retry = True
                continue
            if retry:
                self._logger.error("Succesful reconnection!")
            break

    def start_pipe(self):
        self._logger.debug(f"FFMPEG decoder command: {' '.join(self.build_command())}")
        self._pipe = self.pipe()

    def close_pipe(self):
        self._pipe.terminate()
        self._pipe.communicate()

    def read(self):
        return Frame(self._pipe.stdout.read(self._frame_bytes), self.width, self.height)


class FFMPEGCamera:
    def __init__(self, config):
        self._logger = logging.getLogger(__name__ + "." + config.camera.name_slug)
        self._config = config
        self._connected = False
        self._connection_error = False
        self.resolution = None
        self._segments = None
        self.frame_ready = Event()
        self.scan_for_objects = Event()  # Set when frame should be scanned
        self.scan_for_motion = Event()  # Set when frame should be scanned

        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(True)

        self.initialize_camera()

    def initialize_camera(self):
        self._logger = logging.getLogger(__name__ + "." + self._config.camera.name_slug)
        if getattr(self._config.camera.logging, "level", None):
            self._logger.setLevel(self._config.camera.logging.level)

        self._logger.debug(f"Initializing camera {self._config.camera.name}")

        if self._config.camera.substream:
            self.stream = Stream(
                self._logger,
                self._config,
                self._config.camera.substream,
                write_segments=False,
                pipe_frames=True,
            )
            self._segments = Stream(
                self._logger,
                self._config,
                self._config.camera,
                write_segments=True,
                pipe_frames=False,
            )
        else:
            self.stream = Stream(
                self._logger,
                self._config,
                self._config.camera,
                write_segments=True,
                pipe_frames=True,
            )

        self.resolution = self.stream.width, self.stream.height
        self._logger.debug(
            f"Resolution: {self.resolution[0]}x{self.resolution[1]} "
            f"@ {self.stream.fps} FPS"
        )
        self._logger.debug(f"Camera {self._config.camera.name} initialized")

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

        self.stream.start_pipe()
        if self._segments:
            self._segments.start_pipe()

        object_frame_number = 0
        object_first_scan = False
        object_decoder_interval_calculated = round(
            object_decoder_interval * self.stream.fps
        )
        self._logger.debug(
            f"Running object detection at {object_decoder_interval}s interval, "
            f"every {object_decoder_interval_calculated} frame(s)"
        )

        motion_frame_number = 0
        motion_decoder_interval_calculated = round(
            motion_decoder_interval * self.stream.fps
        )
        self._logger.debug(
            f"Running motion detection at {motion_decoder_interval}s interval, "
            f"every {motion_decoder_interval_calculated} frame(s)"
        )

        while self._connected:
            if self._connection_error:
                sleep(5)
                self._logger.error("Restarting frame pipe")
                self.stream.close_pipe()
                self.stream.check_command()
                self.stream.start_pipe()
                self._connection_error = False

            current_frame = self.stream.read()
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

        self.stream.close_pipe()
        if self._segments:
            self._segments.close_pipe()
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
