# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import collections
import math

import numpy as np
from pkg_resources import parse_version
from edgetpu import __version__ as edgetpu_version
assert parse_version(edgetpu_version) >= parse_version('2.11.1'), \
        'This demo requires Edge TPU version >= 2.11.1'

from edgetpu.basic.basic_engine import BasicEngine
from edgetpu.utils import image_processing
from PIL import Image

KEYPOINTS = (
  'nose',
  'left eye',
  'right eye',
  'left ear',
  'right ear',
  'left shoulder',
  'right shoulder',
  'left elbow',
  'right elbow',
  'left wrist',
  'right wrist',
  'left hip',
  'right hip',
  'left knee',
  'right knee',
  'left ankle',
  'right ankle'
)

class Keypoint:
    __slots__ = ['k', 'yx', 'score']

    def __init__(self, k, yx, score=None):
        self.k = k
        self.yx = yx
        self.score = score

    def __repr__(self):
        return 'Keypoint(<{}>, {}, {})'.format(KEYPOINTS[self.k], self.yx, self.score)


class Pose:
    __slots__ = ['keypoints', 'score']

    def __init__(self, keypoints, score=None):
        assert len(keypoints) == len(KEYPOINTS)
        self.keypoints = keypoints
        self.score = score

    def __repr__(self):
        return 'Pose({}, {})'.format(self.keypoints, self.score)


class PoseEngine(BasicEngine):
    """Engine used for pose tasks."""

    def __init__(self, model_path, mirror=False):
        """Creates a PoseEngine with given model.

        Args:
          model_path: String, path to TF-Lite Flatbuffer file.
          mirror: Flip keypoints horizontally

        Raises:
          ValueError: An error occurred when model output is invalid.
        """
        BasicEngine.__init__(self, model_path)
        self._mirror = mirror

        self._input_tensor_shape = self.get_input_tensor_shape()
        if (self._input_tensor_shape.size != 4 or
                self._input_tensor_shape[3] != 3 or
                self._input_tensor_shape[0] != 1):
            raise ValueError(
                ('Image model should have input shape [1, height, width, 3]!'
                 ' This model has {}.'.format(self._input_tensor_shape)))
        _, self.image_height, self.image_width, self.image_depth = self.get_input_tensor_shape()

        # The API returns all the output tensors flattened and concatenated. We
        # have to figure out the boundaries from the tensor shapes & sizes.
        offset = 0
        self._output_offsets = [0]
        for size in self.get_all_output_tensors_sizes():
            offset += size
            self._output_offsets.append(offset)

    def DetectPosesInImage(self, img):
        """Detects poses in a given image.

           For ideal results make sure the image fed to this function is close to the
           expected input size - it is the caller's responsibility to resize the
           image accordingly.

        Args:
          img: numpy array containing image
        """

        # Extend or crop the input to match the input shape of the network.
        if img.shape[0] < self.image_height or img.shape[1] < self.image_width:
            img = np.pad(img, [[0, max(0, self.image_height - img.shape[0])],
                               [0, max(0, self.image_width - img.shape[1])], [0, 0]],
                         mode='constant')
        img = img[0:self.image_height, 0:self.image_width]
        assert (img.shape == tuple(self._input_tensor_shape[1:]))

        # Run the inference (API expects the data to be flattened)
        inference_time, output = self.RunInference(img.flatten())
        outputs = [output[i:j] for i, j in zip(self._output_offsets, self._output_offsets[1:])]

        keypoints = outputs[0].reshape(-1, len(KEYPOINTS), 2)
        keypoint_scores = outputs[1].reshape(-1, len(KEYPOINTS))
        pose_scores = outputs[2]
        nposes = int(outputs[3][0])
        assert nposes < outputs[0].shape[0]

        # Convert the poses to a friendlier format of keypoints with associated
        # scores.
        poses = []
        for pose_i in range(nposes):
            keypoint_dict = {}
            for point_i, point in enumerate(keypoints[pose_i]):
                keypoint = Keypoint(KEYPOINTS[point_i], point,
                                    keypoint_scores[pose_i, point_i])
                if self._mirror: keypoint.yx[1] = self.image_width - keypoint.yx[1]
                keypoint_dict[KEYPOINTS[point_i]] = keypoint
            poses.append(Pose(keypoint_dict, pose_scores[pose_i]))

        return poses, inference_time