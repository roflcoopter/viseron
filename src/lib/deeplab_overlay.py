import numpy as np
import cv2
from PIL import Image

DEEPLAB_PALETTE = Image.open("/src/app/colorpalette.png").getpalette()


def deeplab_overlay_on_image(frames, result):

    color_image = frames.get()

    if isinstance(result, type(None)):
        return color_image
    img_cp = color_image.copy()

    outputimg = np.reshape(np.uint8(result), (513, 513))
    #outputimg = cv2.resize(outputimg, (513, 513))
    outputimg = Image.fromarray(outputimg, mode="P")
    outputimg.putpalette(DEEPLAB_PALETTE)
    outputimg = outputimg.convert("RGB")
    outputimg = np.asarray(outputimg)
    outputimg = cv2.cvtColor(outputimg, cv2.COLOR_RGB2BGR)
    img_cp = cv2.addWeighted(img_cp, 1.0, outputimg, 0.9, 0)

    return img_cp


def create_pascal_label_colormap():
    """Creates a label colormap used in PASCAL VOC segmentation benchmark.

    Returns:
      A Colormap for visualizing segmentation results.
    """
    colormap = np.zeros((256, 3), dtype=int)
    ind = np.arange(256, dtype=int)

    for shift in reversed(range(8)):
        for channel in range(3):
            colormap[:, channel] |= ((ind >> channel) & 1) << shift
        ind >>= 3

    return colormap


def label_to_color_image(label):
    """Adds color defined by the dataset colormap to the label.

    Args:
      label: A 2D array with integer type, storing the segmentation label.

    Returns:
      result: A 2D array with floating type. The element of the array
        is the color indexed by the corresponding element in the input label
        to the PASCAL color map.

    Raises:
      ValueError: If label is not of rank 2 or its value is larger than color
        map maximum entry.
    """
    if label.ndim != 2:
        raise ValueError('Expect 2-D input label')

    colormap = create_pascal_label_colormap()

    if np.max(label) >= len(colormap):
        raise ValueError('label value too large.')

    return colormap[label]


def vis_segmentation(image, seg_map):
    """Visualizes input image, segmentation map and overlay view."""
    seg_map = np.reshape(np.uint8(seg_map), (513, 513))

    seg_image = label_to_color_image(seg_map).astype(np.uint8)

    unique_labels, label_count = np.unique(seg_map, return_counts=True)
    unique_labels_list = zip(unique_labels, label_count)
    text_y = 0
    for label in unique_labels_list:
        text = "{}: {}".format(label[0], label[1])
        text_y += 25
        cv2.putText(seg_image, text, (10, text_y), cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255), 1)
    #print(FULL_COLOR_MAP[unique_labels].astype(np.uint8))
    return (seg_image)



LABEL_NAMES = np.asarray([
    'background', 'aeroplane', 'bicycle', 'bird', 'boat', 'bottle', 'bus',
    'car', 'cat', 'chair', 'cow', 'diningtable', 'dog', 'horse', 'motorbike',
    'person', 'pottedplant', 'sheep', 'sofa', 'train', 'tv'
])

FULL_LABEL_MAP = np.arange(len(LABEL_NAMES)).reshape(len(LABEL_NAMES), 1)
FULL_COLOR_MAP = label_to_color_image(FULL_LABEL_MAP)
