import datetime
import logging
import os
import subprocess as sp
from queue import Empty

import config

LOGGER = logging.getLogger(__name__)


class FFMPEGRecorder(object):
    def __init__(self):
        LOGGER.info('Initializing ffmpeg recorder')
        self.is_recording = False
        self.writer_pipe = None
        return

    def write_frames(self, file_name, frame_buffer, width, height, fps):
        command = ['/root/bin/ffmpeg',
                   '-loglevel', 'panic',
                   '-hwaccel', 'vaapi', '-vaapi_device', '/dev/dri/renderD128',
                   '-threads', '8',
                   '-y',
                   '-f', 'rawvideo', '-pix_fmt', 'nv12', '-s:v',
                   '{}x{}'.format(width, height),
                   '-r', str(fps), '-i', 'pipe:0',
                   '-an',
                   '-vf', 'format=nv12|vaapi,hwupload',
                   '-vcodec', 'h264_vaapi',
                   '-qp', '19', '-bf', '2',
                   file_name]
        LOGGER.debug('Filename: {}'.format(file_name))

        writer_pipe = sp.Popen(command,
                               stdin=sp.PIPE,
                               bufsize=int(width*height*1.5))

        while self.is_recording:
            try:
                frame = frame_buffer.get(timeout=1)
#                LOGGER.debug("Writing frame of size {} to file."
#                             .format(sys.getsizeof(frame)))
                writer_pipe.stdin.write(frame['frame'])
            except Empty:
                LOGGER.error("Timed out")

        writer_pipe.terminate()
        writer_pipe.wait()
        LOGGER.info('FFMPEG recorder stopped')

    def subfolder_name(self, today):
        return "{:04}-{:02}-{:02}".format(today.year, today.month, today.day)

    def start_recording(self, frame_buffer, width, height, fps):
        LOGGER.info('Starting recorder')
        self.is_recording = True

        if config.OUTPUT_DIRECTORY is None:
            LOGGER.error("Output directory is not specified")
            return

        # Create filename
        now = datetime.datetime.now()
        file_name = "{}{}".format(now.strftime(
            "%H:%M:%S"), config.OUTPUT_FILES_EXTENSION)

        # Create foldername
        subfolder = self.subfolder_name(now)
        full_path = os.path.normpath(os.path.join(
            config.OUTPUT_DIRECTORY, "./{}".format(subfolder)))
        try:
            if not os.path.isdir(full_path):
                LOGGER.info('Creating folder {}'.format(full_path))
                os.makedirs(full_path)
            else:
                LOGGER.info('Folder already exists')
        except FileExistsError:
            LOGGER.error('Folder already exists')

        self.write_frames(os.path.join(full_path, file_name),
                          frame_buffer, width, height, fps)

    def stop(self):
        LOGGER.info('Stopping recorder')
        self.is_recording = False
        return
