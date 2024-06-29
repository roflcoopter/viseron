"""Dummy setup.py so that pip does not try to install opencv-python-headless."""
from setuptools import setup, find_packages

OPENCV_VERSION=

setup(
    name="opencv-python-headless",
    version=OPENCV_VERSION,
    packages=find_packages(),
    install_requires=[],
)