"""General helper functions."""
from __future__ import annotations

import datetime
import linecache
import logging
import math
import multiprocessing as mp
import os
import re
import socket
import time
import tracemalloc
import urllib.parse
from queue import Full, Queue
from typing import TYPE_CHECKING, Any, Literal, overload

import cv2
import numpy as np
import slugify as unicode_slug
import supervision as sv
import tornado.queues as tq

from viseron.const import FONT, FONT_SIZE, FONT_THICKNESS

if TYPE_CHECKING:
    from viseron.domains.object_detector.detected_object import DetectedObject

LOGGER = logging.getLogger(__name__)


def utcnow() -> datetime.datetime:
    """Return current UTC time."""
    return datetime.datetime.now(tz=datetime.timezone.utc)


def get_utc_offset() -> datetime.timedelta:
    """Return the current UTC offset."""
    return datetime.timedelta(seconds=time.localtime().tm_gmtoff)


def daterange_to_utc(
    date: str, utc_offset: datetime.timedelta
) -> tuple[datetime.datetime, datetime.datetime]:
    """Convert date range to UTC.

    The result is independent of the timezone of the server.
    It is adjusted to the clients timezone by subtracting the utc_offset.
    """
    time_from = (
        datetime.datetime.strptime(date, "%Y-%m-%d").replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=datetime.timezone.utc
        )
        - utc_offset
    )
    time_to = time_from + datetime.timedelta(
        hours=23, minutes=59, seconds=59, microseconds=999999
    )
    return time_from, time_to


def calculate_relative_contours(
    contours, resolution: tuple[int, int]
) -> list[np.ndarray]:
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
    bounding_box: tuple[float, float, float, float], frame_res: tuple[int, int]
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

    filter_text = ""
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


def _annotate_frame(
    frame: np.ndarray,
    bounding_boxes: np.ndarray,
    class_ids: np.ndarray,
    labels: list[str] | None,
) -> np.ndarray:
    """Annotate a frame with bounding boxes and labels."""
    detections = sv.Detections(xyxy=bounding_boxes, class_id=class_ids)
    box_corner_annotator = sv.BoxCornerAnnotator(corner_length=20, thickness=4)
    label_annotator = sv.LabelAnnotator(
        text_scale=1.0, border_radius=5, text_thickness=2
    )

    annotated_image = box_corner_annotator.annotate(scene=frame, detections=detections)
    annotated_image = label_annotator.annotate(
        scene=annotated_image, detections=detections, labels=labels
    )
    return annotated_image


def annotate_frame(
    frame: np.ndarray,
    bounding_box: tuple[int, int, int, int],
    label: str | None = None,
) -> np.ndarray:
    """Annotate a frame with a single bounding box and label."""
    _bounding_box = np.array(
        [
            [
                bounding_box[0],
                bounding_box[1],
                bounding_box[2],
                bounding_box[3],
            ]
        ]
    )
    return _annotate_frame(
        frame, _bounding_box, np.array([0]), [label] if label else None
    )


def _get_object_text(detected_object: DetectedObject) -> str:
    """Return text to be displayed for an object."""
    text = f"{detected_object.label.title()} {int(detected_object.confidence * 100)}%"
    if detected_object.filter_hit:
        text += f"\nFilter: {detected_object.filter_hit}"
    return text


def draw_objects(
    frame: np.ndarray,
    detected_objects: list[DetectedObject],
    resolution: tuple[int, int] | None = None,
) -> None:
    """Draw objects on supplied frame."""
    if resolution:
        bounding_boxes = np.array(
            [
                list(
                    calculate_absolute_coords(
                        (
                            detected_object.rel_x1,
                            detected_object.rel_y1,
                            detected_object.rel_x2,
                            detected_object.rel_y2,
                        ),
                        resolution,
                    )
                )
                for detected_object in detected_objects
            ]
        )
    else:
        bounding_boxes = np.array(
            [
                [
                    detected_object.abs_x1,
                    detected_object.abs_y1,
                    detected_object.abs_x2,
                    detected_object.abs_y2,
                ]
                for detected_object in detected_objects
            ]
        )
    class_id = np.array([index for index, _ in enumerate(detected_objects)])
    labels = [_get_object_text(detected_object) for detected_object in detected_objects]
    _annotate_frame(frame, bounding_boxes, class_id, labels)


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


def draw_mask(
    text: str,
    frame: np.ndarray,
    mask_points: list[np.ndarray],
    color: tuple[int, int, int] = (255, 255, 255),
) -> None:
    """Draw mask on supplied frame."""
    mask_overlay: np.ndarray = frame.copy()
    # Draw polygon filled with black color
    cv2.fillPoly(
        mask_overlay,
        pts=mask_points,
        color=(0, 0, 0),  # Specify the color as a tuple of three integers
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


def apply_mask(frame: np.ndarray, mask_image) -> None:
    """Apply mask to frame."""
    frame[mask_image] = [0]


def pop_if_full(
    queue: Queue | mp.Queue | tq.Queue,
    item: Any,
    logger: logging.Logger = LOGGER,
    name: str = "unknown",
    warn: bool = False,
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


def create_directory(path: str) -> None:
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


def generate_mask_image(mask, resolution):
    """Return an image with the mask drawn on it."""
    mask_image = np.zeros(
        (
            resolution[0],
            resolution[1],
            3,
        ),
        np.uint8,
    )
    mask_image[:] = 255

    cv2.fillPoly(mask_image, pts=mask, color=(0, 0, 0))
    return np.where(mask_image[:, :, 0] == [0])


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
        image, (output_width, output_height), interpolation=cv2.INTER_AREA
    )
    output_image = np.full((height, width, 3), 0, dtype="uint8")
    output_image[
        (height - output_height) // 2 : (height - output_height) // 2 + output_height,
        (width - output_width) // 2 : (width - output_width) // 2 + output_width,
        :,
    ] = image.copy()
    return output_image


@overload
def convert_letterboxed_bbox(
    frame_width: int,
    frame_height: int,
    model_width: int,
    model_height: int,
    bbox: tuple[int, int, int, int],
    return_absolute: Literal[False] = ...,
) -> tuple[float, float, float, float]:
    ...


@overload
def convert_letterboxed_bbox(
    frame_width: int,
    frame_height: int,
    model_width: int,
    model_height: int,
    bbox: tuple[int, int, int, int],
    return_absolute: Literal[True],
) -> tuple[int, int, int, int]:
    ...


def convert_letterboxed_bbox(
    frame_width: int,
    frame_height: int,
    model_width: int,
    model_height: int,
    bbox: tuple[int, int, int, int],
    return_absolute: bool = False,
) -> tuple[float, float, float, float] | tuple[int, int, int, int]:
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
        model_width:
            Width of object detection model.
        model_height:
            Height of object detection model.
        bbox:
            The ABSOLUTE bounding box coordinates predicted from the model.
        return_absolute:
            If True, return absolute coordinates. If False, return relative coordinates.

    Returns:
        The converted relative or absolute bounding box coordinates.
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
        new_x1 = (
            x1 / model_width
        ) * frame_width  # Scale width from model to frame width
        new_x2 = (
            x2 / model_width
        ) * frame_width  # Scale width from model to frame width
        new_y1 = (
            (y1 - 1 / 2 * (model_height - frame_height / frame_width * model_height))
            * frame_width
            / model_width
        )
        new_y2 = (
            (y2 - 1 / 2 * (model_height - frame_height / frame_width * model_height))
            * frame_width
            / model_width
        )
    else:  # Vertical padding
        new_x1 = (
            (x1 - 1 / 2 * (model_height - frame_width / frame_height * model_height))
            * frame_height
            / model_width
        )
        new_x2 = (
            (x2 - 1 / 2 * (model_height - frame_width / frame_height * model_height))
            * frame_height
            / model_width
        )
        new_y1 = (
            y1 / model_height * frame_height
        )  # Scale height from model to frame height
        new_y2 = (
            y2 / model_height * frame_height
        )  # Scale height from model to frame height
    if return_absolute:
        return (
            round(new_x1),
            round(new_y1),
            round(new_x2),
            round(new_y2),
        )

    return calculate_relative_coords(
        (
            round(new_x1),
            round(new_y1),
            round(new_x2),
            round(new_y2),
        ),
        (frame_width, frame_height),
    )


def zoom_boundingbox(
    frame: np.ndarray,
    bounding_box: tuple[int, int, int, int],
    min_size=300,
    crop_correction_factor=1,
) -> np.ndarray:
    """Zoom in on a bounding box in an image."""
    x1, y1, x2, y2 = bounding_box
    size = max(int(max(x2 - x1, y2 - y1) * crop_correction_factor), min_size)

    x_offset = max(
        0, min(int((x2 - x1) / 2.0 + x1 - size / 2.0), frame.shape[1] - size)
    )
    y_offset = max(
        0, min(int((y2 - y1) / 2.0 + y1 - size / 2.0), frame.shape[0] - size)
    )

    return frame.copy()[y_offset : y_offset + size, x_offset : x_offset + size]


def get_free_port(port=1024, max_port=65535) -> int:
    """Find a free port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while port <= max_port:
        try:
            sock.bind(("", port))
            sock.close()
            return port
        except OSError:
            port += 1
    raise OSError("no free ports")


def escape_string(string: str) -> str:
    """Escape special characters in a string."""
    return urllib.parse.quote(string, safe="")


def parse_size_to_bytes(size_str: str) -> int:
    """Convert human-readable size strings to bytes (e.g. '10mb' -> 10485760)."""

    units = {
        "tb": 1024**4,
        "gb": 1024**3,
        "mb": 1024**2,
        "kb": 1024,
        "b": 1,
    }

    size_str = str(size_str).strip().lower()

    # If it's just a number, assume bytes
    if size_str.isdigit():
        return int(size_str)

    # Extract number and unit
    for unit in units:
        if size_str.endswith(unit):
            try:
                number = float(size_str[: -len(unit)])
                return int(number * units[unit])
            except ValueError as err:
                raise ValueError(f"Invalid size format: {size_str}") from err

    raise ValueError(
        f"Invalid size unit in {size_str}. Must be one of: {', '.join(units.keys())}"
    )


def get_image_files_in_folder(folder) -> list[str]:
    """Return all files with JPG, JPEG or PNG extension."""
    return [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if re.match(r".*\.(jpg|jpeg|png)", f, flags=re.I)
    ]


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
