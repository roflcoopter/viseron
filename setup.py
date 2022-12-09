"""Viseron setup script."""
from setuptools import setup

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="viseron",
    version="0.0.0",
    description="Viseron - Self-hosted, local only NVR with object detection",
    license="MIT",
    long_description=long_description,
    author="roflcoopter",
    url="https://github.com/roflcoopter/viseron",
    packages=["viseron"],
)
