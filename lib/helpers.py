import math
from queue import Full, Queue
from typing import Any, Tuple

import cv2


def calculate_relative_coords(
    bounding_box: Tuple[int, int, int, int], resolution: Tuple[int, int]
) -> Tuple[float, float, float, float]:
    x1_relative = bounding_box[0] / resolution[0]
    y1_relative = bounding_box[1] / resolution[1]
    x2_relative = bounding_box[2] / resolution[0]
    y2_relative = bounding_box[3] / resolution[1]
    return x1_relative, y1_relative, x2_relative, y2_relative


def draw_bounding_box_relative(frame, bounding_box, frame_res):
    topleft = (
        math.floor(bounding_box[0] * frame_res[0]),
        math.floor(bounding_box[1] * frame_res[1]),
    )
    bottomright = (
        math.floor(bounding_box[2] * frame_res[0]),
        math.floor(bounding_box[3] * frame_res[1]),
    )
    return cv2.rectangle(frame, topleft, bottomright, (255, 0, 0), 5)


def scale_bounding_box(image_size, bounding_box, target_size):
    """Scales a bounding box to target image size"""
    x1p = bounding_box[0] / image_size[0]
    y1p = bounding_box[1] / image_size[1]
    x2p = bounding_box[2] / image_size[0]
    y2p = bounding_box[3] / image_size[1]
    return (
        x1p * target_size[0],
        y1p * target_size[1],
        x2p * target_size[0],
        y2p * target_size[1],
    )


def pop_if_full(queue: Queue, item: Any):
    """If queue is full, pop oldest item and put the new item"""
    try:
        queue.put_nowait(item)
    except Full:
        queue.get()
        queue.put_nowait(item)
