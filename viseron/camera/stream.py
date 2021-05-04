import json
import os
import subprocess as sp
from time import sleep

from viseron.const import CAMERA_SEGMENT_ARGS
from viseron.exceptions import FFprobeError, StreamInformationError

from .frame import Frame


class Stream:
    """Represents a stream of frames from a camera."""

    def __init__(
        self, logger, config, stream_config, write_segments=True, pipe_frames=True
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
            or not self.stream_config.audio_codec
        ):
            (
                width,
                height,
                fps,
                stream_codec,
                audio_codec,
            ) = self.get_stream_information(self.stream_config.stream_url)

        self.width = self.stream_config.width if self.stream_config.width else width
        self.height = self.stream_config.height if self.stream_config.height else height
        self.fps = self.stream_config.fps if self.stream_config.fps else fps
        self.stream_codec = stream_codec
        self.audio_codec = audio_codec

        if self.width and self.height and self.fps:
            pass
        else:
            raise StreamInformationError(self.width, self.height, self.fps)

        self._frame_bytes = int(self.width * self.height * 1.5)

    @staticmethod
    def run_ffprobe(stream_url: str, stream_type: str) -> dict:
        """Run FFprobe command."""
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
            stream_type,
        ] + [stream_url]

        pipe = sp.Popen(ffprobe_command, stdout=sp.PIPE)
        stdout, _ = pipe.communicate()
        pipe.wait()
        output: dict = json.loads(stdout)

        if output.get("error", None):
            raise FFprobeError(output)

        return output

    def ffprobe_stream_information(self, stream_url):
        """Return stream information using FFprobe."""
        width, height, fps, codec, audio_codec = 0, 0, 0, None, None
        video_streams = self.run_ffprobe(stream_url, "v")
        audio_streams = self.run_ffprobe(stream_url, "a")

        for stream in audio_streams["streams"]:
            audio_codec = stream.get("codec_name", None)

        try:
            stream_information = video_streams["streams"][0]
            numerator = int(stream_information.get("avg_frame_rate", 0).split("/")[0])
            denominator = int(stream_information.get("avg_frame_rate", 0).split("/")[1])
        except KeyError:
            return (width, height, fps, codec, audio_codec)

        try:
            fps = numerator / denominator
        except ZeroDivisionError:
            pass

        width = stream_information.get("width", 0)
        height = stream_information.get("height", 0)
        codec = stream_information.get("codec_name", None)

        return (width, height, fps, codec, audio_codec)

    def get_stream_information(self, stream_url):
        """Return stream information."""
        self._logger.debug("Getting stream information for {}".format(stream_url))
        width, height, fps, codec, audio_codec = self.ffprobe_stream_information(
            stream_url
        )

        self._logger.debug(
            "Stream information from FFprobe: "
            f"Width: {width} "
            f"Height: {height} "
            f"FPS: {fps} "
            f"Video Codec: {codec} "
            f"Audio Codec: {audio_codec}"
        )
        return width, height, fps, codec, audio_codec

    @staticmethod
    def get_codec(stream_config, stream_codec):
        """Return codec set in config or from predefined codec map."""
        if stream_config.codec:
            return stream_config.codec

        if stream_codec:
            codec = stream_config.codec_map.get(stream_codec, None)
            if codec:
                return ["-c:v", codec]

        return []

    def stream_command(self, stream_config, stream_codec):
        """Return FFmpeg input stream."""
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
        """Return full FFmpeg command."""
        camera_segment_args = []
        if not single_frame and self._write_segments:
            camera_segment_args = (
                CAMERA_SEGMENT_ARGS
                + (["-c:a", "copy"] if self.audio_codec else [])
                + [
                    os.path.join(
                        self._config.recorder.segments_folder,
                        self._config.camera.name,
                        f"%Y%m%d%H%M%S.{self._config.recorder.extension}",
                    )
                ]
            )

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
            + (self._config.camera.filter_args if self._pipe_frames else [])
            + (self._config.camera.output_args if self._pipe_frames else [])
        )

    def pipe(self, stderr=False, single_frame=False):
        """Return subprocess pipe for FFmpeg."""
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
        """Check if generated FFmpeg command works."""
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
                self._logger.error("Successful reconnection!")
            break

    def start_pipe(self):
        """Start piping frames from FFmpeg."""
        self._logger.debug(f"FFMPEG decoder command: {' '.join(self.build_command())}")
        self._pipe = self.pipe()

    def close_pipe(self):
        """Close FFmpeg pipe."""
        self._pipe.terminate()
        self._pipe.communicate()

    def read(self):
        """Return a single frame from FFmpeg pipe."""
        return Frame(self._pipe.stdout.read(self._frame_bytes), self.width, self.height)
