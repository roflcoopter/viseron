"""Motion contours."""
import cv2

from viseron.helpers import calculate_relative_contours


class Contours:
    """Represents motion contours."""

    def __init__(self, contours, resolution):
        self._contours = contours
        self._rel_contours = calculate_relative_contours(contours, resolution)

        scale_factor = resolution[0] * resolution[1]
        self._contour_areas = [cv2.contourArea(c) / scale_factor for c in contours]
        self._max_area = round(max(self._contour_areas, default=0), 5)

    @property
    def contours(self):
        """Return motion contours."""
        return self._contours

    @property
    def rel_contours(self):
        """Return contours with relative coordinates."""
        return self._rel_contours

    @property
    def contour_areas(self):
        """Return size of contours."""
        return self._contour_areas

    @property
    def max_area(self):
        """Return the size of the biggest contour."""
        return self._max_area
