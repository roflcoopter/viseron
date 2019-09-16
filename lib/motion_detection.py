import cv2
import imutils


class MotionDetection(object):
    def __init__(self):
        self.avg = None

    def detect(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        gray = gray.get()  # Convert from UMat to Mat

        # if the average frame is None, initialize it
        if self.avg is None:
            self.avg = gray.astype("float")
            return 0

        # accumulate the weighted average between the current frame and
        # previous frames, then compute the difference between the current
        # frame and running average.
        # Lower value makes the motion detection more sensitive.
        cv2.accumulateWeighted(gray, self.avg, 0.1)
        frame_delta = cv2.absdiff(gray, cv2.convertScaleAbs(self.avg))

        # threshold the delta image, dilate the thresholded image to fill
        # in holes, then find contours on thresholded image
        thresh = cv2.threshold(frame_delta, 5, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        cnts = cv2.findContours(thresh,
                                cv2.RETR_EXTERNAL,
                                cv2.CHAIN_APPROX_SIMPLE)
        cnts = imutils.grab_contours(cnts)

        max_contour = max([cv2.contourArea(c) for c in cnts], default=0)
        return max_contour
