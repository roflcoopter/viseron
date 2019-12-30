import sys
import cv2

sys.path.append("/src/viseron")

import cuda_test
import motion_detection_test

print("---- Starting benchmarks ----")
print("-- Running motion detection tests --")
# motion_detection_test.motion_detection_test()
if cv2.ocl.haveOpenCL():
    print("- Running OpenCL test -")
    cv2.ocl.setUseOpenCL(True)
    motion_detection_test.motion_detection_test()
# motion_detection_test.cuda_motion_detection_test()
# cuda_test.cuda_test()
