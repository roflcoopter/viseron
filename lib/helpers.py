from queue import Full


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


def pop_if_full(queue, item):
    """If queue is full, pop oldest item and put the new item"""
    try:
        queue.put_nowait(item)
    except Full:
        queue.get()
        queue.put_nowait(item)
