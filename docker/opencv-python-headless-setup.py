"""Dummy setup.py so that pip does not try to install opencv-python-headless."""
from setuptools import find_packages, setup

OPENCV_VERSION = "TBD"

setup(
    name="opencv-python-headless",
    version=OPENCV_VERSION,
    packages=find_packages(),
    install_requires=[],
)
