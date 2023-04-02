"""General helper functions."""
from __future__ import annotations

import linecache
import logging
import math
import os
import tracemalloc
from queue import Full, Queue
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np
import slugify as unicode_slug
import tornado.queues as tq

from viseron.const import FONT, FONT_SIZE, FONT_THICKNESS

if TYPE_CHECKING:
    from viseron.domains.object_detector.detected_object import DetectedObject

LOGGER = logging.getLogger(__name__)


def calculate_relative_contours(contours, resolution: tuple[int, int]):
    """Convert contours with absolute coords to relative."""
    relative_contours = []
    for contour in contours:
        relative_contours.append(np.divide(contour, resolution))

    return relative_contours


def calculate_relative_coords(
    bounding_box: tuple[int, int, int, int], resolution: tuple[int, int]
) -> tuple[float, float, float, float]:
    """Convert absolute coords to relative."""
    x1_relative = round(bounding_box[0] / resolution[0], 3)
    y1_relative = round(bounding_box[1] / resolution[1], 3)
    x2_relative = round(bounding_box[2] / resolution[0], 3)
    y2_relative = round(bounding_box[3] / resolution[1], 3)
    return x1_relative, y1_relative, x2_relative, y2_relative


def calculate_absolute_coords(
    bounding_box: tuple[int, int, int, int], frame_res: tuple[int, int]
) -> tuple[int, int, int, int]:
    """Convert relative coords to absolute."""
    return (
        math.floor(bounding_box[0] * frame_res[0]),
        math.floor(bounding_box[1] * frame_res[1]),
        math.floor(bounding_box[2] * frame_res[0]),
        math.floor(bounding_box[3] * frame_res[1]),
    )


def scale_bounding_box(
    image_size: tuple[int, int, int, int],
    bounding_box: tuple[int, int, int, int],
    target_size,
) -> tuple[float, float, float, float]:
    """Scale a bounding box to target image size."""
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
) -> Any:
    """Draw a bounding box using relative coordinates."""
    topleft = (
        math.floor(bounding_box[0] * frame_res[0]),
        math.floor(bounding_box[1] * frame_res[1]),
    )
    bottomright = (
        math.floor(bounding_box[2] * frame_res[0]),
        math.floor(bounding_box[3] * frame_res[1]),
    )
    return cv2.rectangle(frame, topleft, bottomright, color, thickness)


def put_object_label_relative(frame, obj, frame_res, color=(255, 0, 0)) -> None:
    """Draw a label using relative coordinates."""
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
        text=text,
        fontFace=FONT,
        fontScale=FONT_SIZE,
        thickness=FONT_THICKNESS,
    )[0]

    filter_text = None
    if obj.filter_hit:
        filter_text = f"Filter: {obj.filter_hit}"
        (filter_text_width, filter_text_height) = cv2.getTextSize(
            text=filter_text,
            fontFace=FONT,
            fontScale=FONT_SIZE,
            thickness=FONT_THICKNESS,
        )[0]
        text_width = max(text_width, filter_text_width)
        text_height += filter_text_height + 6

    box_coords = (
        (coordinates[0], coordinates[1] + 5),
        (coordinates[0] + text_width + 2, coordinates[1] - text_height - 3),
    )

    cv2.rectangle(frame, box_coords[0], box_coords[1], color, cv2.FILLED)
    if obj.filter_hit:
        cv2.putText(
            img=frame,
            text=text,
            org=(coordinates[0], coordinates[1] - filter_text_height - 6),
            fontFace=FONT,
            fontScale=FONT_SIZE,
            color=(255, 255, 255),
            thickness=FONT_THICKNESS,
        )
        cv2.putText(
            img=frame,
            text=filter_text,
            org=coordinates,
            fontFace=FONT,
            fontScale=FONT_SIZE,
            color=(255, 255, 255),
            thickness=FONT_THICKNESS,
        )
    else:
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
    frame, obj, camera_resolution: tuple[int, int], color=(150, 0, 0), thickness=1
) -> None:
    """Draw a single object on supplied frame."""
    if obj.relevant:
        color = (0, 150, 0)
    frame = draw_bounding_box_relative(
        frame,
        (
            obj.rel_x1,
            obj.rel_y1,
            obj.rel_x2,
            obj.rel_y2,
        ),
        camera_resolution,
        color=color,
        thickness=thickness,
    )
    put_object_label_relative(frame, obj, camera_resolution, color=color)


def draw_objects(frame, objects, camera_resolution) -> None:
    """Draw objects on supplied frame."""
    for obj in objects:
        draw_object(frame, obj, camera_resolution)


def draw_zones(frame, zones) -> None:
    """Draw zones on supplied frame."""
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


def draw_contours(frame, contours, resolution, threshold) -> None:
    """Draw contours on supplied frame."""
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


def draw_mask(text, frame, mask_points, color=(255, 255, 255)) -> None:
    """Draw mask on supplied frame."""
    mask_overlay = frame.copy()
    # Draw polygon filled with black color
    cv2.fillPoly(
        mask_overlay,
        pts=mask_points,
        color=(0),
    )
    # Apply overlay on frame with 70% opacity
    cv2.addWeighted(
        mask_overlay,
        0.7,
        frame,
        1 - 0.7,
        0,
        frame,
    )
    # Draw polygon outline
    cv2.polylines(frame, mask_points, True, color, 2)
    try:
        for mask in mask_points:
            image_moment = cv2.moments(mask)
            center_x = int(image_moment["m10"] / image_moment["m00"])
            center_y = int(image_moment["m01"] / image_moment["m00"])
            text_size = cv2.getTextSize(
                text=text,
                fontFace=FONT,
                fontScale=FONT_SIZE,
                thickness=FONT_THICKNESS,
            )[0]
            cv2.putText(
                frame,
                text,
                (center_x - (int(text_size[0] / 2)), center_y + 5),
                FONT,
                FONT_SIZE,
                (255, 255, 255),
                FONT_THICKNESS,
            )
    except ZeroDivisionError:
        LOGGER.warning("Center of mask could not be calculated. No text will be drawn.")


def draw_motion_mask(frame, mask_points) -> None:
    """Draw motion mask."""
    draw_mask("Motion mask", frame, mask_points, color=(0, 140, 255))


def draw_object_mask(frame, mask_points) -> None:
    """Draw object mask."""
    draw_mask("Object mask", frame, mask_points, color=(255, 255, 255))


def pop_if_full(
    queue: Queue, item: Any, logger=LOGGER, name="unknown", warn=False
) -> None:
    """If queue is full, pop oldest item and put the new item."""
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


def create_directory(path) -> None:
    """Create a directory."""
    try:
        if not os.path.isdir(path):
            LOGGER.debug(f"Creating folder {path}")
            os.makedirs(path)
    except FileExistsError:
        pass


def generate_numpy_from_coordinates(points):
    """Return a numpy array for a list of x+y coordinates."""
    point_list = []
    for point in points:
        point_list.append([point["x"], point["y"]])
    return np.array(point_list)


def generate_mask(coordinates):
    """Return a mask used to limit motion or object detection to specific areas."""
    mask = []
    for mask_coordinates in coordinates:
        mask.append(generate_numpy_from_coordinates(mask_coordinates["coordinates"]))
    return mask


def object_in_polygon(resolution, obj: DetectedObject, coordinates):
    """Check if a DetectedObject is within a boundary."""
    x1, _, x2, y2 = calculate_absolute_coords(
        (
            obj.rel_x1,
            obj.rel_y1,
            obj.rel_x2,
            obj.rel_y2,
        ),
        resolution,
    )
    middle = ((x2 - x1) / 2) + x1
    return cv2.pointPolygonTest(coordinates, (middle, y2), False) >= 0


def letterbox_resize(image: np.ndarray, width, height):
    """Resize image to expected size, keeping aspect ratio and pad with black pixels."""
    image_height, image_width, _ = image.shape
    scale = min(height / image_height, width / image_width)
    output_height = int(image_height * scale)
    output_width = int(image_width * scale)

    image = cv2.resize(
        image, (output_width, output_height), interpolation=cv2.INTER_CUBIC
    )
    output_image = np.full((height, width, 3), 0, dtype="uint8")
    output_image[
        (height - output_height) // 2 : (height - output_height) // 2 + output_height,
        (width - output_width) // 2 : (width - output_width) // 2 + output_width,
        :,
    ] = image.copy()
    return output_image


def convert_letterboxed_bbox(
    frame_width, frame_height, model_width, model_height, bbox
):
    """Convert boundingbox from a letterboxed image to the original image.

    To improve accuracy, images are resized with letterboxing before running
    object detection. This avoids distorting the image.
    When an image is letterboxed, the bbox does not correspond 1-to-1 with the original
    image, so we need to convert the coordinates
    Args:
        frame_width:
            Width of original input image.
        frame_height:
            Height of original input image.
        frame_width:
            Width of object detection model.
        frame_height:
            Height of object detection model.
        bbox:
            The ABSOLUTE bounding box coordinates predicted from the model.
    """
    if model_width != model_height:
        raise ValueError(
            "Can only convert bbox from a letterboxed image for models of equal "
            f"width and height, got {model_width}x{model_height}",
        )
    x1, y1, x2, y2 = bbox

    scale = min(model_height / frame_height, model_width / frame_width)
    output_height = int(frame_height * scale)
    output_width = int(frame_width * scale)

    if output_width > output_height:  # Horizontal padding
        y1 = (
            (y1 - 1 / 2 * (model_height - frame_height / frame_width * model_height))
            * frame_width
            / model_width
        )
        y2 = (
            (y2 - 1 / 2 * (model_height - frame_height / frame_width * model_height))
            * frame_width
            / model_width
        )
        return (
            (x1 / model_width) * frame_width,  # Scale width from model to frame width
            y1,
            (x2 / model_width) * frame_width,  # Scale width from model to frame width
            y2,
        )

    # Vertical padding
    x1 = (
        (x1 - 1 / 2 * (model_height - frame_width / frame_height * model_height))
        * frame_height
        / model_width
    )
    x2 = (
        (x2 - 1 / 2 * (model_height - frame_width / frame_height * model_height))
        * frame_height
        / model_width
    )
    return (
        x1,
        (y1 / model_height) * frame_height,  # Scale height from model to frame height
        x2,
        (y2 / model_height) * frame_height,  # Scale height from model to frame height
    )


def memory_usage_profiler(logger, key_type="lineno", limit=5) -> None:
    """Print a table with the lines that are using the most memory."""
    snapshot = tracemalloc.take_snapshot()
    snapshot = snapshot.filter_traces(
        (
            tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
            tracemalloc.Filter(False, "<unknown>"),
        )
    )
    top_stats = snapshot.statistics(key_type)

    log_message = "Memory profiler:"
    log_message += "\nTop %s lines" % limit
    for index, stat in enumerate(top_stats[:limit], 1):
        frame = stat.traceback[0]
        # replace "/path/to/module/file.py" with "module/file.py"
        filename = os.sep.join(frame.filename.split(os.sep)[-2:])
        log_message += "\n#{}: {}:{}: {:.1f} KiB".format(
            index,
            filename,
            frame.lineno,
            stat.size / 1024,
        )
        line = linecache.getline(frame.filename, frame.lineno).strip()
        if line:
            log_message += "\n    %s" % line

    other = top_stats[limit:]
    if other:
        size = sum(stat.size for stat in other)
        log_message += f"\n{len(other)} other: {size / 1024:.1f} KiB"
    total = sum(stat.size for stat in top_stats)
    log_message += "\nTotal allocated size: %.1f KiB" % (total / 1024)
    log_message += "\n----------------------------------------------------------------"
    logger.debug(log_message)
