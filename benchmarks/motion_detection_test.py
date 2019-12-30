from lib.motion import MotionDetection
import numpy as np
import cv2
from line_profiler import LineProfiler


def motion_detection_test():
    dummy_event = "Event"
    motion_detector = MotionDetection(dummy_event, 500, 1)
    image = np.random.randint(255, size=(900, 800, 3), dtype=np.uint8)
    umat_image = cv2.UMat(image)

    lp = LineProfiler()
    lp_wrapper = lp(motion_detector.detect)

    for i in range(1000):
        lp_wrapper(umat_image)

    lp.print_stats()


def cuda_motion_detection(image):
    background_subtractor = cv2.cuda.createBackgroundSubtractorMOG2(100, 16, False)

    learning_rate = 0.05
    gpu_device = cv2.cuda_GpuMat()

    gpu_device.upload(image)
    fgmask = background_subtractor.apply(
        gpu_device, learning_rate, cv2.cuda.Stream_Null()
    )
    # contours, _ = cv2.findContours(
    #     fgmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    # )


def cuda_motion_detection_test():
    dummy_event = "Event"
    image = np.random.randint(255, size=(900, 800, 3), dtype=np.uint8)

    lp = LineProfiler()
    lp_wrapper = lp(cuda_motion_detection)

    for i in range(1000):
        lp_wrapper(image)

    lp.print_stats()
