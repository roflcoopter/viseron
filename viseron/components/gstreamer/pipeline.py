"""GStreamer pipelines."""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from viseron.components.ffmpeg.const import (
    CAMERA_SEGMENT_DURATION,
    CONFIG_SEGMENTS_FOLDER,
)
from viseron.domains.camera.const import CONFIG_EXTENSION

from .const import (
    COMPONENT,
    CONFIG_AUDIO_CODEC,
    CONFIG_AUDIO_PIPELINE,
    CONFIG_GSTREAMER_LOGLEVEL,
    CONFIG_MUXER,
    CONFIG_OUTPUT_ELEMENT,
    CONFIG_RAW_PIPELINE,
    CONFIG_RECORDER,
    CONFIG_RTSP_TRANSPORT,
    CONFIG_STREAM_FORMAT,
    DECODER_ELEMENT_MAP,
    DEFAULT_AUDIO_PIPELINE,
    DEPAY_ELEMENT_MAP,
    GSTREAMER_LOGLEVELS,
    PARSE_ELEMENT_MAP,
    PIXEL_FORMAT,
    STREAM_FORMAT_MAP,
)

if TYPE_CHECKING:
    from viseron.components.gstreamer.stream import Stream


class AbstractPipeline(ABC):
    """Abstract GStreamer pipeline."""

    @abstractmethod
    def build_pipeline(self):
        """Build pipeline."""


class RawPipeline(AbstractPipeline):
    """Raw GStreamer pipeline."""

    def __init__(self, vis, config, stream: Stream, camera_identifier):
        self._vis = vis
        self._config = config
        self._stream = stream
        self._camera = vis.data[COMPONENT][camera_identifier]

    def build_pipeline(self):
        """Build pipeline."""
        return self._config[CONFIG_RAW_PIPELINE].split(" ")


class BasePipeline(AbstractPipeline):
    """Base GStreamer pipeline."""

    def __init__(self, vis, config, stream: Stream, camera_identifier):
        self._vis = vis
        self._config = config
        self._stream = stream
        self._camera = vis.data[COMPONENT][camera_identifier]

    def global_args(self):
        """Return GStreamer global args."""
        return [self._stream.alias] + [
            (
                "--gst-debug-level="
                f"{GSTREAMER_LOGLEVELS[self._config[CONFIG_GSTREAMER_LOGLEVEL]]}"
            ),
            "-q",
        ]

    def input_pipeline(self):
        """Generate GStreamer input pipeline."""
        return (
            [STREAM_FORMAT_MAP[self._config[CONFIG_STREAM_FORMAT]]["plugin"]]
            + [f"location={self._stream.output_stream_url}"]
            + [
                "name=input_stream",
                "do-timestamp=true",
            ]
            + STREAM_FORMAT_MAP[self._config[CONFIG_STREAM_FORMAT]]["options"]
            + (
                [
                    f"protocols={self._config[CONFIG_RTSP_TRANSPORT]}",
                    "!",
                    "rtpjitterbuffer",
                    "do-lost=true",
                    "drop-on-latency=true",
                ]
                if self._config[CONFIG_STREAM_FORMAT] == "rtsp"
                else []
            )
        )

    def depay_element(self):
        """Return depay element.

        Returns depay element from override map if it exists.
        Otherwise we assume the depay element shares name with the codec.
        """
        if depay_element := DEPAY_ELEMENT_MAP.get(self._stream.stream_codec, None):
            _depay_element = ["!", depay_element]
        elif depay_element is False:
            return ["!"]
        else:
            _depay_element = ["!", f"rtp{self._stream.stream_codec}depay"]

        return _depay_element + [
            "!",
            "tee",
            "name=depayed_stream",
            "!",
            "queue",
            "!",
        ]

    def videorate_element(self):
        """Return videorate element to limit fps."""
        if self._stream.output_fps < self._stream.fps:
            return [
                "videorate",
                "!",
                f"video/x-raw,framerate={int(self._stream.output_fps)}/1",
                "!",
            ]
        return []

    def output_element(self):
        """Return output element to apply user defined options."""
        return self._config[CONFIG_OUTPUT_ELEMENT].split(" ")

    @staticmethod
    def converter_element():
        """Return converter element.

        The converter element is used to convert input stream to raw image
        """
        return [
            "videoconvert",
            "!",
        ]

    def decoder_element(self):
        """Return decoder element.

        Returns decoder element from override map if it exists.
        Otherwise we assume the decoder element shares name with the codec.
        """
        decoder_element = DECODER_ELEMENT_MAP.get(self._stream.stream_codec, None)

        if decoder_element is False:
            return []
        if decoder_element:
            return [
                decoder_element,
                "!",
            ]
        return [
            f"avdec_{self._stream.stream_codec}",
            "!",
        ]

    def output_pipeline(self):
        """Generate GStreamer output pipeline."""
        return (
            self.depay_element()
            + self.decoder_element()
            + self.videorate_element()
            + self.output_element()
            + self.converter_element()
            + [
                f"video/x-raw,format=(string){PIXEL_FORMAT}",
                "!",
                "fdsink",
                "depayed_stream.",
            ]
        )

    def parse_element(self):
        """Return parse element.

        Returns parse element from override map if it exists.
        Otherwise we assume the parse element shares name with the codec.
        """
        if parse_element := PARSE_ELEMENT_MAP.get(self._stream.stream_codec, None):
            return ["!", parse_element]

        return ["!", f"{self._stream.stream_codec}parse"]

    def segment_pipeline(self):
        """Generate GStreamer segment args."""
        segment_filepattern = os.path.join(
            self._config[CONFIG_RECORDER][CONFIG_SEGMENTS_FOLDER],
            self._camera.identifier,
            f"%01d.{self._config[CONFIG_RECORDER][CONFIG_EXTENSION]}",
        )
        return (
            [
                "!",
                "queue",
            ]
            + self.parse_element()
            + [
                "!",
                "splitmuxsink",
                "async-finalize=true",
                "send-keyframe-requests=true",
                "max-size-bytes=0",
                "name=mux",
                f"muxer={self._config[CONFIG_RECORDER][CONFIG_MUXER]}",
                f"max-size-time={str(CAMERA_SEGMENT_DURATION)}000000000",
            ]
            + [f"location={segment_filepattern}"]
        )

    def audio_pipeline(self):
        """Return audio pipeline."""
        if (
            self._stream.output_stream_config[CONFIG_AUDIO_PIPELINE]
            and self._stream.output_stream_config[CONFIG_AUDIO_PIPELINE]
            != DEFAULT_AUDIO_PIPELINE
        ):
            return self._stream.output_stream_config[CONFIG_AUDIO_PIPELINE].split(" ")

        if (
            self._stream.output_stream_config[CONFIG_AUDIO_CODEC]
            and self._stream.output_stream_config[CONFIG_AUDIO_CODEC]
            != DEFAULT_AUDIO_PIPELINE
        ) or (
            self._stream.stream_audio_codec
            and self._stream.output_stream_config[CONFIG_AUDIO_CODEC]
        ):
            return [
                "input_stream.",
                "!",
                "queue",
                "!",
                "decodebin",
                "!",
                "audioconvert",
                "!",
                "queue",
                "!",
                "voaacenc",
                "!",
                "mux.audio_0",
            ]

        return []

    def build_pipeline(self):
        """Return pipeline."""
        return (
            self.global_args()
            + self.input_pipeline()
            + self.output_pipeline()
            + self.segment_pipeline()
            + self.audio_pipeline()
        )


class JetsonPipeline(BasePipeline):
    """Jetson specific pipeline."""

    def videorate_element(self):
        """Dont create videorate element.

        Handled by drop-frame-interval in decoder_element.
        """
        return []

    def decoder_element(self):
        """Return decoder element.

        Returns decoder element from override map if it exists.
        Otherwise we assume the decoder element shares name with the codec.
        """
        return [
            "nvv4l2decoder",
            "enable-max-performance=true",
            f"drop-frame-interval={int(self._stream.fps/self._stream.output_fps)}",
            "!",
        ]

    @staticmethod
    def converter_element():
        """Return converter element.

        The converter element is used to convert input stream to raw image
        """
        return [
            "nvvidconv",
            "!",
        ]
