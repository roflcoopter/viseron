"""Darknet wrapper.

Adapted from https://github.com/AlexeyAB/darknet/blob/master/darknet.py
"""

from ctypes import (
    CDLL,
    POINTER,
    RTLD_GLOBAL,
    Structure,
    c_char_p,
    c_float,
    c_int,
    c_void_p,
    pointer,
)


class BOX(Structure):
    """Boudning box."""

    _fields_ = [("x", c_float), ("y", c_float), ("w", c_float), ("h", c_float)]


class DETECTION(Structure):
    """Detected object."""

    _fields_ = [
        ("bbox", BOX),
        ("classes", c_int),
        ("best_class_idx", c_int),
        ("prob", POINTER(c_float)),
        ("mask", POINTER(c_float)),
        ("objectness", c_float),
        ("sort_class", c_int),
        ("uc", POINTER(c_float)),
        ("points", c_int),
        ("embeddings", POINTER(c_float)),
        ("embedding_size", c_int),
        ("sim", c_float),
        ("track_id", c_int),
    ]


class DETNUMPAIR(Structure):
    """Detection pair."""

    _fields_ = [("num", c_int), ("dets", POINTER(DETECTION))]


class IMAGE(Structure):
    """Darkent image."""

    _fields_ = [("w", c_int), ("h", c_int), ("c", c_int), ("data", POINTER(c_float))]


class METADATA(Structure):
    """Label metadata."""

    _fields_ = [("classes", c_int), ("names", POINTER(c_char_p))]


class DarknetWrapper:
    """Wrapper around Darknet C library."""

    def __init__(self, half_precision) -> None:
        library = "libdarknet_half.so" if half_precision else "libdarknet.so"
        self._lib = CDLL(library, RTLD_GLOBAL)

        self._lib.network_width.argtypes = [c_void_p]
        self._lib.network_width.restype = c_int
        self._lib.network_height.argtypes = [c_void_p]
        self._lib.network_height.restype = c_int

        self.copy_image_from_bytes = self._lib.copy_image_from_bytes
        self.copy_image_from_bytes.argtypes = [IMAGE, c_char_p]

        self._predict = self._lib.network_predict_ptr
        self._predict.argtypes = [c_void_p, POINTER(c_float)]
        self._predict.restype = POINTER(c_float)

        self._set_gpu = self._lib.cuda_set_device
        self._init_cpu = self._lib.init_cpu

        self.make_image = self._lib.make_image
        self.make_image.argtypes = [c_int, c_int, c_int]
        self.make_image.restype = IMAGE

        self._get_network_boxes = self._lib.get_network_boxes
        self._get_network_boxes.argtypes = [
            c_void_p,
            c_int,
            c_int,
            c_float,
            c_float,
            POINTER(c_int),
            c_int,
            POINTER(c_int),
            c_int,
        ]
        self._get_network_boxes.restype = POINTER(DETECTION)

        self._make_network_boxes = self._lib.make_network_boxes
        self._make_network_boxes.argtypes = [c_void_p]
        self._make_network_boxes.restype = POINTER(DETECTION)

        self._free_detections = self._lib.free_detections
        self._free_detections.argtypes = [POINTER(DETECTION), c_int]

        self._free_batch_detections = self._lib.free_batch_detections
        self._free_batch_detections.argtypes = [POINTER(DETNUMPAIR), c_int]

        self._free_ptrs = self._lib.free_ptrs
        self._free_ptrs.argtypes = [POINTER(c_void_p), c_int]

        self._network_predict = self._lib.network_predict_ptr
        self._network_predict.argtypes = [c_void_p, POINTER(c_float)]

        self._reset_rnn = self._lib.reset_rnn
        self._reset_rnn.argtypes = [c_void_p]

        self._load_net = self._lib.load_network
        self._load_net.argtypes = [c_char_p, c_char_p, c_int]
        self._load_net.restype = c_void_p

        self._load_net_custom = self._lib.load_network_custom
        self._load_net_custom.argtypes = [c_char_p, c_char_p, c_int, c_int]
        self._load_net_custom.restype = c_void_p

        self._free_network_ptr = self._lib.free_network_ptr
        self._free_network_ptr.argtypes = [c_void_p]
        self._free_network_ptr.restype = c_void_p

        self._do_nms_obj = self._lib.do_nms_obj
        self._do_nms_obj.argtypes = [POINTER(DETECTION), c_int, c_int, c_float]

        self._do_nms_sort = self._lib.do_nms_sort
        self._do_nms_sort.argtypes = [POINTER(DETECTION), c_int, c_int, c_float]

        self._free_image = self._lib.free_image
        self._free_image.argtypes = [IMAGE]

        self._letterbox_image = self._lib.letterbox_image
        self._letterbox_image.argtypes = [IMAGE, c_int, c_int]
        self._letterbox_image.restype = IMAGE

        self._load_meta = self._lib.get_metadata
        self._lib.get_metadata.argtypes = [c_char_p]
        self._lib.get_metadata.restype = METADATA

        self._load_image = self._lib.load_image_color
        self._load_image.argtypes = [c_char_p, c_int, c_int]
        self._load_image.restype = IMAGE

        self._rgbgr_image = self._lib.rgbgr_image
        self._rgbgr_image.argtypes = [IMAGE]

        self._predict_image = self._lib.network_predict_image
        self._predict_image.argtypes = [c_void_p, IMAGE]
        self._predict_image.restype = POINTER(c_float)

        self._predict_image_letterbox = self._lib.network_predict_image_letterbox
        self._predict_image_letterbox.argtypes = [c_void_p, IMAGE]
        self._predict_image_letterbox.restype = POINTER(c_float)

        self._network_predict_batch = self._lib.network_predict_batch
        self._network_predict_batch.argtypes = [
            c_void_p,
            IMAGE,
            c_int,
            c_int,
            c_int,
            c_float,
            c_float,
            POINTER(c_int),
            c_int,
            c_int,
        ]
        self._network_predict_batch.restype = POINTER(DETNUMPAIR)

    def load_network(self, config_file, data_file, weights, batch_size=1):
        """Load model description and weights from config files.

        args:
            config_file (str): path to .cfg model file
            data_file (str): path to .data model file
            weights (str): path to weights
        returns:
            network: trained model
            class_names
        """
        network = self._load_net_custom(
            config_file.encode("ascii"), weights.encode("ascii"), 0, batch_size
        )
        metadata = self._load_meta(data_file.encode("ascii"))
        class_names = [
            metadata.names[i].decode("ascii") for i in range(metadata.classes)
        ]
        return network, class_names

    def detect_image(
        self, network, class_names, image, thresh=0.5, hier_thresh=0.5, nms=0.45
    ):
        """Return a list with highest confidence class and their bbox."""
        pnum = pointer(c_int(0))
        self._predict_image(network, image)
        detections = self._get_network_boxes(
            network, image.w, image.h, thresh, hier_thresh, None, 0, pnum, 0
        )
        num = pnum[0]
        if nms:
            self._do_nms_sort(detections, num, len(class_names), nms)
        predictions = remove_negatives(detections, class_names, num)
        predictions = decode_detection(predictions)
        self._free_detections(detections, num)
        return sorted(predictions, key=lambda x: x[1])


def remove_negatives(detections, class_names, num):
    """Remove all classes with 0% confidence within the detection."""
    predictions = []
    for j in range(num):
        for idx, name in enumerate(class_names):
            if detections[j].prob[idx] > 0:
                bbox = detections[j].bbox
                bbox = (bbox.x, bbox.y, bbox.w, bbox.h)
                predictions.append((name, detections[j].prob[idx], (bbox)))
    return predictions


def decode_detection(detections):
    """Decode detections."""
    decoded = []
    for label, confidence, bbox in detections:
        confidence = str(round(confidence, 2))
        decoded.append((str(label), confidence, bbox))
    return decoded
