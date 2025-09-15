"""Utility functions for Hailo."""


import logging
import multiprocessing as mp
import os
import subprocess as sp
import urllib.request
from typing import Any, Literal
from urllib.parse import urlparse

import numpy as np

from viseron.components.hailo.const import HAILO8_DEFAULT_URL, HAILO8L_DEFAULT_URL
from viseron.domains.object_detector.const import MODEL_CACHE

LOGGER = logging.getLogger(__name__)


def get_hailo_arch() -> None | Literal["hailo8l"] | Literal["hailo8"]:
    """Return detected Hailo device architecture."""
    cmd = ["hailortcli", "fw-control", "identify"]
    try:
        result = sp.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        LOGGER.error("hailortcli not found in PATH while detecting Hailo architecture")
        return None
    except Exception:  # pylint: disable=broad-except
        LOGGER.exception("Unexpected error while detecting Hailo architecture")
        return None

    if result.returncode != 0:
        LOGGER.error(
            "Failed running '%s': returncode=%s stderr=%s",
            " ".join(cmd),
            result.returncode,
            result.stderr.strip(),
        )
        return None

    for line in result.stdout.splitlines():
        if "Device Architecture" in line:
            lowered = line.lower()
            if "hailo8l" in lowered:
                return "hailo8l"
            if "hailo8" in lowered:
                return "hailo8"
            break

    LOGGER.error("Could not determine Hailo architecture from hailortcli output")
    return None


def load_labels(labels: str) -> list[str]:
    """Load labels from file."""
    with open(labels, encoding="utf-8") as labels_file:
        return labels_file.read().rstrip("\n").split("\n")


def get_model_size(process_queue: mp.Queue):
    """Get model size by sending a job to the subprocess."""
    process_queue.put("get_model_size")


def inference_callback(
    completion_info,
    bindings_list: list,
    item: dict[str, Any],
) -> None:
    """Inference callback to handle inference results."""
    if completion_info.exception:
        LOGGER.error(f"Inference error: {completion_info.exception}")
        return

    for _, bindings in enumerate(bindings_list):
        if len(bindings._output_names) == 1:  # pylint: disable=protected-access
            result = bindings.output().get_buffer()
        else:
            result = {
                name: np.expand_dims(bindings.output(name).get_buffer(), axis=0)
                for name in bindings._output_names  # pylint: disable=protected-access
            }
        item["result"] = result


def is_url(value: str) -> bool:
    """Return True if value appears to be an HTTP(S) URL."""
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"}


def get_model_name(model_path: str) -> str:
    """Return model filename."""
    return os.path.basename(model_path)


def download_model(url: str, cached_model_path: str) -> None:
    """Download model to cache."""
    if not url.endswith(".hef"):
        raise ValueError("Invalid model URL. Only .hef files are supported.")
    try:
        urllib.request.urlretrieve(url, cached_model_path)
        LOGGER.info(f"Downloaded model to {cached_model_path}")
    except Exception as e:
        raise RuntimeError(f"Failed to download model from {url}: {str(e)}") from e


def get_model(model_path: str | None, hailo_arch: Literal["hailo8", "hailo8l"]) -> str:
    """Return locally cached model or download if a URL is provided."""
    if model_path is None:
        if hailo_arch == "hailo8l":
            model_path = HAILO8L_DEFAULT_URL
        else:
            model_path = HAILO8_DEFAULT_URL

    os.makedirs(MODEL_CACHE, exist_ok=True)
    path_is_url = is_url(model_path)

    # Search for local path
    if not path_is_url:
        if not model_path.endswith(".hef"):
            raise ValueError(f"Provided model path must end with .hef: {model_path}")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found at: {model_path}")
        LOGGER.debug("Using provided model file %s", model_path)
        return model_path

    # Determine model name and cache destination
    model_name = get_model_name(model_path)
    cached_model_path = os.path.join(MODEL_CACHE, model_name)

    # Search for cached path
    if os.path.exists(cached_model_path):
        LOGGER.debug("Using cached model %s", cached_model_path)
        return cached_model_path

    LOGGER.info("Downloading model %s -> %s", model_path, cached_model_path)
    download_model(model_path, cached_model_path)
    return cached_model_path
