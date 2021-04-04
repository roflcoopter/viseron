""" General helper functions """
import logging
import math
from collections import Counter
from queue import Full, Queue
from typing import Any, Callable, Dict, Hashable, Tuple

import numpy as np
import tornado.queues as tq
import voluptuous as vol

import cv2
import slugify as unicode_slug
from const import FONT, FONT_SIZE, FONT_THICKNESS

LOGGER = logging.getLogger(__name__)


def calculate_relative_contours(contours, resolution: Tuple[int, int]):
    relative_contours = []
    for contour in contours:
        relative_contours.append(np.divide(contour, resolution))

    return relative_contours


def calculate_relative_coords(
    bounding_box: Tuple[int, int, int, int], resolution: Tuple[int, int]
) -> Tuple[float, float, float, float]:
    x1_relative = round(bounding_box[0] / resolution[0], 3)
    y1_relative = round(bounding_box[1] / resolution[1], 3)
    x2_relative = round(bounding_box[2] / resolution[0], 3)
    y2_relative = round(bounding_box[3] / resolution[1], 3)
    return x1_relative, y1_relative, x2_relative, y2_relative


def calculate_absolute_coords(
    bounding_box: Tuple[int, int, int, int], frame_res: Tuple[int, int]
) -> Tuple[float, float, float, float]:
    return (
        math.floor(bounding_box[0] * frame_res[0]),
        math.floor(bounding_box[1] * frame_res[1]),
        math.floor(bounding_box[2] * frame_res[0]),
        math.floor(bounding_box[3] * frame_res[1]),
    )


def scale_bounding_box(
    image_size: Tuple[int, int, int, int],
    bounding_box: Tuple[int, int, int, int],
    target_size,
) -> Tuple[float, float, float, float]:
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


def draw_bounding_box_relative(
    frame, bounding_box, frame_res, color=(255, 0, 0), thickness=1
):
    topleft = (
        math.floor(bounding_box[0] * frame_res[0]),
        math.floor(bounding_box[1] * frame_res[1]),
    )
    bottomright = (
        math.floor(bounding_box[2] * frame_res[0]),
        math.floor(bounding_box[3] * frame_res[1]),
    )
    return cv2.rectangle(frame, topleft, bottomright, color, thickness)


def put_object_label_relative(frame, obj, frame_res, color=(255, 0, 0)):
    coordinates = (
        math.floor(obj.rel_x1 * frame_res[0]),
        (math.floor(obj.rel_y1 * frame_res[1])) - 5,
    )

    # If label is outside the top of the frame, put it below the bounding box
    if coordinates[1] < 10:
        coordinates = (
            math.floor(obj.rel_x1 * frame_res[0]),
            (math.floor(obj.rel_y2 * frame_res[1])) + 5,
        )

    text = f"{obj.label} {int(obj.confidence * 100)}%"

    (text_width, text_height) = cv2.getTextSize(
        text=text, fontFace=FONT, fontScale=FONT_SIZE, thickness=FONT_THICKNESS,
    )[0]
    box_coords = (
        (coordinates[0], coordinates[1] + 5),
        (coordinates[0] + text_width + 2, coordinates[1] - text_height - 3),
    )
    cv2.rectangle(frame, box_coords[0], box_coords[1], color, cv2.FILLED)
    cv2.putText(
        img=frame,
        text=text,
        org=coordinates,
        fontFace=FONT,
        fontScale=FONT_SIZE,
        color=(255, 255, 255),
        thickness=FONT_THICKNESS,
    )


def draw_object(
    frame, obj, camera_resolution: Tuple[int, int], color=(150, 0, 0), thickness=1
):
    """ Draws a single object on supplied frame """
    if obj.relevant:
        color = (0, 150, 0)
    frame = draw_bounding_box_relative(
        frame,
        (obj.rel_x1, obj.rel_y1, obj.rel_x2, obj.rel_y2,),
        camera_resolution,
        color=color,
        thickness=thickness,
    )
    put_object_label_relative(frame, obj, camera_resolution, color=color)


def draw_objects(frame, objects, camera_resolution):
    """ Draws objects on supplied frame """
    for obj in objects:
        draw_object(frame, obj, camera_resolution)


def draw_zones(frame, zones):
    for zone in zones:
        if zone.objects_in_zone:
            color = (0, 255, 0)
        else:
            color = (0, 0, 255)
        cv2.polylines(frame, [zone.coordinates], True, color, 2)

        cv2.putText(
            frame,
            zone.name,
            (zone.coordinates[0][0] + 5, zone.coordinates[0][1] + 15),
            FONT,
            FONT_SIZE,
            color,
            FONT_THICKNESS,
        )


def draw_contours(frame, contours, resolution, threshold):
    filtered_contours = []
    relevant_contours = []
    for relative_contour, area in zip(contours.rel_contours, contours.contour_areas):
        abs_contour = np.multiply(relative_contour, resolution).astype("int32")
        if area > threshold:
            relevant_contours.append(abs_contour)
            continue
        filtered_contours.append(abs_contour)

    cv2.drawContours(frame, relevant_contours, -1, (255, 0, 255), thickness=2)
    cv2.drawContours(frame, filtered_contours, -1, (130, 0, 75), thickness=1)


def draw_mask(frame, mask_points):
    mask_overlay = frame.copy()
    # Draw polygon filled with black color
    cv2.fillPoly(
        mask_overlay, pts=mask_points, color=(0),
    )
    # Apply overlay on frame with 70% opacity
    cv2.addWeighted(
        mask_overlay, 0.7, frame, 1 - 0.7, 0, frame,
    )
    # Draw polygon outline in orange
    cv2.polylines(frame, mask_points, True, (0, 140, 255), 2)
    for mask in mask_points:
        image_moment = cv2.moments(mask)
        center_x = int(image_moment["m10"] / image_moment["m00"])
        center_y = int(image_moment["m01"] / image_moment["m00"])
        cv2.putText(
            frame,
            "Mask",
            (center_x - 20, center_y + 5),
            FONT,
            FONT_SIZE,
            (255, 255, 255),
            FONT_THICKNESS,
        )


def pop_if_full(queue: Queue, item: Any, logger=LOGGER, name="unknown", warn=False):
    """If queue is full, pop oldest item and put the new item"""
    try:
        queue.put_nowait(item)
    except (Full, tq.QueueFull):
        if warn:
            logger.warning(f"{name} queue is full. Removing oldest entry")
        queue.get()
        queue.put_nowait(item)


def slugify(text: str) -> str:
    """Slugify a given text."""
    return unicode_slug.slugify(text, separator="_")


def print_slugs(config: dict):
    """Prints all camera names as slugs."""
    cameras = config["cameras"]
    for camera in cameras:
        print(
            f"Name: {camera['name']}, "
            f"slug: {unicode_slug.slugify(camera['name'], separator='_')}"
        )


def report_labels(
    labels, labels_in_fov, reported_label_count, mqtt_queue, mqtt_devices
):
    labels = sorted(labels)
    if labels == labels_in_fov:
        return labels_in_fov, reported_label_count

    labels_added = list(set(labels) - set(labels_in_fov))
    labels_removed = list(set(labels_in_fov) - set(labels))

    # Count occurences of each label
    counter = Counter(labels)

    if mqtt_queue:
        for label in labels_added:
            attributes = {}
            attributes["count"] = counter[label]
            mqtt_devices[label].publish(True, attributes)
            reported_label_count[label] = counter[label]  # Save reported count

        for label in labels_removed:
            mqtt_devices[label].publish(False)

        for label, count in counter.items():
            if reported_label_count.get(label, 0) != count:
                attributes = {}
                attributes["count"] = count
                mqtt_devices[label].publish(True, attributes)
                reported_label_count[label] = count

    return labels, reported_label_count


def combined_objects(frame, zones):
    """ Combine the object lists of a frame and all zones """
    all_objects = frame.objects if frame else []
    for zone in zones:
        all_objects += zone.objects_in_zone
    return all_objects


class Filter:
    def __init__(self, object_filter):
        self._label = object_filter.label
        self._confidence = object_filter.confidence
        self._width_min = object_filter.width_min
        self._width_max = object_filter.width_max
        self._height_min = object_filter.height_min
        self._height_max = object_filter.height_max
        self._triggers_recording = object_filter.triggers_recording
        self._require_motion = object_filter.require_motion
        self._post_processor = object_filter.post_processor

    def filter_confidence(self, obj):
        if obj.confidence > self._confidence:
            return True
        return False

    def filter_width(self, obj):
        if self._width_max > obj.rel_width > self._width_min:
            return True
        return False

    def filter_height(self, obj):
        if self._height_max > obj.rel_height > self._height_min:
            return True
        return False

    def filter_object(self, obj):
        return (
            self.filter_confidence(obj)
            and self.filter_width(obj)
            and self.filter_height(obj)
        )

    @property
    def triggers_recording(self):
        return self._triggers_recording

    def require_motion(self):
        return self._require_motion

    @property
    def post_processor(self):
        return self._post_processor


def key_dependency(
    key: Hashable, dependency: Hashable
) -> Callable[[Dict[Hashable, Any]], Dict[Hashable, Any]]:
    """Validate that all dependencies exist for key."""

    def validator(value: Dict[Hashable, Any]) -> Dict[Hashable, Any]:
        """Test dependencies."""
        if not isinstance(value, dict):
            raise vol.Invalid("key dependencies require a dict")
        if key in value and dependency not in value:
            raise vol.Invalid(
                f'dependency violation - key "{key}" requires '
                f'key "{dependency}" to exist'
            )

        return value

    return validator
