"""Test the Tune API handler."""
from __future__ import annotations

import json
import os
from unittest.mock import patch

import yaml

from tests.components.webserver.common import TestAppBaseAuth


class TestTuneAPIHandler(TestAppBaseAuth):
    """Test the TuneAPIHandler."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

        # Use a test config file in the test directory
        self.config_path = os.path.join(
            os.path.dirname(__file__), "test_tune_config.yaml"
        )

        # Sample config structure in JSON
        self.sample_config = {
            "darknet": {
                "object_detector": {
                    "cameras": {
                        "camera_1": {
                            "labels": [
                                {
                                    "label": "person",
                                    "confidence": 0.8,
                                    "trigger_event_recording": True,
                                },
                                {
                                    "label": "car",
                                    "confidence": 0.7,
                                    "trigger_event_recording": False,
                                },
                            ],
                            "zones": [
                                {
                                    "name": "zone_1",
                                    "coordinates": [
                                        {"x": 0, "y": 0},
                                        {"x": 100, "y": 0},
                                        {"x": 100, "y": 100},
                                        {"x": 0, "y": 100},
                                    ],
                                    "labels": [
                                        {
                                            "label": "person",
                                            "confidence": 0.9,
                                        }
                                    ],
                                }
                            ],
                            "mask": [
                                {
                                    "coordinates": [
                                        {"x": 10, "y": 10},
                                        {"x": 50, "y": 10},
                                        {"x": 50, "y": 50},
                                    ],
                                }
                            ],
                            "fps": 5,
                        },
                        "camera_2": {
                            "labels": [
                                {
                                    "label": "dog",
                                    "confidence": 0.75,
                                    "trigger_event_recording": True,
                                }
                            ],
                        },
                    }
                }
            },
            "mog2": {
                "motion_detector": {
                    "cameras": {
                        "camera_1": {
                            "mask": [
                                {
                                    "coordinates": [
                                        {"x": 20, "y": 20},
                                        {"x": 60, "y": 20},
                                        {"x": 60, "y": 60},
                                    ],
                                }
                            ],
                            "threshold": 15,
                        }
                    }
                }
            },
            "dlib": {
                "face_recognition": {
                    "cameras": {
                        "camera_1": {
                            "labels": ["John Doe", "Jane Smith"],
                            "mask": [
                                {
                                    "coordinates": [
                                        {"x": 30, "y": 30},
                                        {"x": 70, "y": 30},
                                        {"x": 70, "y": 70},
                                    ],
                                }
                            ],
                        }
                    }
                }
            },
            "codeprojectai": {
                "license_plate_recognition": {
                    "cameras": {
                        "camera_1": {
                            "labels": ["ABC-1234", "XYZ-5678"],
                            "mask": [
                                {
                                    "coordinates": [
                                        {"x": 40, "y": 40},
                                        {"x": 80, "y": 40},
                                        {"x": 80, "y": 80},
                                    ],
                                }
                            ],
                        }
                    }
                }
            },
            "ffmpeg": {
                "camera": {
                    "camera_1": {
                        "name": "Front Door",
                        "host": "localhost",
                        "port": 8554,
                        "path": "/camera_1",
                        "width": 1920,
                        "height": 1080,
                    }
                }
            },
        }

        # Write sample config to temp file
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self.sample_config, f, default_flow_style=False, sort_keys=False)

    def tearDown(self) -> None:
        """Tear down test fixtures."""
        # Clean up temp config file
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
        super().tearDown()

    def test_get_all_camera_tune(self) -> None:
        """Test getting all camera tune settings."""
        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth("/api/v1/tune", method="GET")

        assert response.code == 200
        data = json.loads(response.body)

        # Verify camera_1 has all domains
        assert "camera_1" in data
        assert "object_detector" in data["camera_1"]
        assert "motion_detector" in data["camera_1"]
        assert "face_recognition" in data["camera_1"]
        assert "license_plate_recognition" in data["camera_1"]
        assert "camera" in data["camera_1"]

        # Verify camera_2 has only object_detector
        assert "camera_2" in data
        assert "object_detector" in data["camera_2"]

        # Verify object_detector structure for camera_1
        obj_detector = data["camera_1"]["object_detector"]["darknet"]
        assert "labels" in obj_detector
        assert "zones" in obj_detector
        assert "mask" in obj_detector
        assert "available_labels" in obj_detector
        assert len(obj_detector["labels"]) == 2
        assert obj_detector["labels"][0]["label"] == "person"

        # Verify face_recognition structure for camera_1
        face_recog = data["camera_1"]["face_recognition"]["dlib"]
        assert "labels" in face_recog
        assert face_recog["labels"] == ["John Doe", "Jane Smith"]
        assert "mask" in face_recog

        # Verify license_plate_recognition structure for camera_1
        plate_recog = data["camera_1"]["license_plate_recognition"]["codeprojectai"]
        assert "labels" in plate_recog
        assert plate_recog["labels"] == ["ABC-1234", "XYZ-5678"]
        assert "mask" in plate_recog

    def test_get_camera_tune(self) -> None:
        """Test getting tune settings for a specific camera."""
        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth("/api/v1/tune/camera_1", method="GET")

        assert response.code == 200
        data = json.loads(response.body)

        # Verify all domains are present
        assert "object_detector" in data
        assert "motion_detector" in data
        assert "face_recognition" in data
        assert "license_plate_recognition" in data
        assert "camera" in data

        # Verify darknet object_detector
        assert "darknet" in data["object_detector"]
        darknet = data["object_detector"]["darknet"]
        assert len(darknet["labels"]) == 2
        assert darknet["labels"][0]["label"] == "person"
        assert darknet["fps"] == 5

    def test_get_camera_tune_not_found(self) -> None:
        """Test getting tune settings for a non-existent camera."""
        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth(
                "/api/v1/tune/non_existent_camera", method="GET"
            )

        assert response.code == 404
        data = json.loads(response.body)
        assert "error" in data
        assert "non_existent_camera" in data["error"]

    def test_update_object_detector_labels(self) -> None:
        """Test updating object detector labels."""
        update_data = {
            "domain": "object_detector",
            "component": "darknet",
            "data": {
                "labels": [
                    {
                        "label": "person",
                        "confidence": 0.9,
                        "trigger_event_recording": True,
                    },
                    {
                        "label": "bicycle",
                        "confidence": 0.85,
                        "trigger_event_recording": False,
                    },
                ]
            },
        }

        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth(
                "/api/v1/tune/camera_1",
                method="PUT",
                body=json.dumps(update_data),
            )

        assert response.code == 200
        data = json.loads(response.body)
        assert data["message"] == "Configuration updated successfully"

        # Verify config was updated
        with open(self.config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        labels = config["darknet"]["object_detector"]["cameras"]["camera_1"]["labels"]
        assert len(labels) == 2
        assert labels[0]["label"] == "person"
        assert labels[0]["confidence"] == 0.9
        assert labels[1]["label"] == "bicycle"
        assert labels[1]["confidence"] == 0.85

    def test_update_object_detector_zones(self) -> None:
        """Test updating object detector zones."""
        update_data = {
            "domain": "object_detector",
            "component": "darknet",
            "data": {
                "zones": [
                    {
                        "name": "new_zone",
                        "coordinates": [
                            {"x": 200, "y": 200},
                            {"x": 300, "y": 200},
                            {"x": 300, "y": 300},
                            {"x": 200, "y": 300},
                        ],
                        "labels": [
                            {
                                "label": "person",
                                "confidence": 0.95,
                            }
                        ],
                    }
                ]
            },
        }

        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth(
                "/api/v1/tune/camera_1",
                method="PUT",
                body=json.dumps(update_data),
            )

        assert response.code == 200

        # Verify config was updated
        with open(self.config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        zones = config["darknet"]["object_detector"]["cameras"]["camera_1"]["zones"]
        assert len(zones) == 1
        assert zones[0]["name"] == "new_zone"

    def test_update_object_detector_mask(self) -> None:
        """Test updating object detector mask."""
        update_data = {
            "domain": "object_detector",
            "component": "darknet",
            "data": {
                "mask": [
                    {
                        "coordinates": [
                            {"x": 150, "y": 150},
                            {"x": 250, "y": 150},
                            {"x": 250, "y": 250},
                        ],
                    }
                ]
            },
        }

        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth(
                "/api/v1/tune/camera_1",
                method="PUT",
                body=json.dumps(update_data),
            )

        assert response.code == 200

        # Verify config was updated
        with open(self.config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        mask = config["darknet"]["object_detector"]["cameras"]["camera_1"]["mask"]
        assert len(mask) == 1

    def test_update_motion_detector_mask(self) -> None:
        """Test updating motion detector mask."""
        update_data = {
            "domain": "motion_detector",
            "component": "mog2",
            "data": {
                "mask": [
                    {
                        "coordinates": [
                            {"x": 100, "y": 100},
                            {"x": 200, "y": 100},
                            {"x": 200, "y": 200},
                        ],
                    }
                ]
            },
        }

        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth(
                "/api/v1/tune/camera_1",
                method="PUT",
                body=json.dumps(update_data),
            )

        assert response.code == 200

        # Verify config was updated
        with open(self.config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        mask = config["mog2"]["motion_detector"]["cameras"]["camera_1"]["mask"]
        assert len(mask) == 1

    def test_update_face_recognition_labels(self) -> None:
        """Test updating face recognition labels."""
        update_data = {
            "domain": "face_recognition",
            "component": "dlib",
            "data": {"labels": ["Alice Cooper", "Bob Marley", "Charlie Brown"]},
        }

        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth(
                "/api/v1/tune/camera_1",
                method="PUT",
                body=json.dumps(update_data),
            )

        assert response.code == 200

        # Verify config was updated
        with open(self.config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        labels = config["dlib"]["face_recognition"]["cameras"]["camera_1"]["labels"]
        assert len(labels) == 3
        assert labels[0] == "Alice Cooper"
        assert labels[1] == "Bob Marley"
        assert labels[2] == "Charlie Brown"

    def test_update_face_recognition_mask(self) -> None:
        """Test updating face recognition mask."""
        update_data = {
            "domain": "face_recognition",
            "component": "dlib",
            "data": {
                "mask": [
                    {
                        "coordinates": [
                            {"x": 50, "y": 50},
                            {"x": 100, "y": 50},
                            {"x": 100, "y": 100},
                        ],
                    }
                ]
            },
        }

        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth(
                "/api/v1/tune/camera_1",
                method="PUT",
                body=json.dumps(update_data),
            )

        assert response.code == 200

        # Verify config was updated
        with open(self.config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        mask = config["dlib"]["face_recognition"]["cameras"]["camera_1"]["mask"]
        assert len(mask) == 1

    def test_update_license_plate_recognition_labels(self) -> None:
        """Test updating license plate recognition labels."""
        update_data = {
            "domain": "license_plate_recognition",
            "component": "codeprojectai",
            "data": {"labels": ["DEF-9012", "GHI-3456", "JKL-7890"]},
        }

        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth(
                "/api/v1/tune/camera_1",
                method="PUT",
                body=json.dumps(update_data),
            )

        assert response.code == 200

        # Verify config was updated
        with open(self.config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        labels = config["codeprojectai"]["license_plate_recognition"]["cameras"][
            "camera_1"
        ]["labels"]
        assert len(labels) == 3
        assert labels[0] == "DEF-9012"
        assert labels[1] == "GHI-3456"
        assert labels[2] == "JKL-7890"

    def test_update_license_plate_recognition_mask(self) -> None:
        """Test updating license plate recognition mask."""
        update_data = {
            "domain": "license_plate_recognition",
            "component": "codeprojectai",
            "data": {
                "mask": [
                    {
                        "coordinates": [
                            {"x": 60, "y": 60},
                            {"x": 120, "y": 60},
                            {"x": 120, "y": 120},
                        ],
                    }
                ]
            },
        }

        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth(
                "/api/v1/tune/camera_1",
                method="PUT",
                body=json.dumps(update_data),
            )

        assert response.code == 200

        # Verify config was updated
        with open(self.config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        mask = config["codeprojectai"]["license_plate_recognition"]["cameras"][
            "camera_1"
        ]["mask"]
        assert len(mask) == 1

    def test_update_camera_config(self) -> None:
        """Test updating camera configuration."""
        update_data = {
            "domain": "camera",
            "component": "ffmpeg",
            "data": {
                "name": "Updated Front Door",
                "host": "localhost",
                "port": 8554,
                "path": "/camera_2",
                "width": 2560,
                "height": 1440,
            },
        }

        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth(
                "/api/v1/tune/camera_1",
                method="PUT",
                body=json.dumps(update_data),
            )

        assert response.code == 200

        # Verify config was updated
        with open(self.config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        camera = config["ffmpeg"]["camera"]["camera_1"]
        assert camera["name"] == "Updated Front Door"
        assert camera["path"] == "/camera_2"
        assert camera["width"] == 2560
        assert camera["height"] == 1440

    def test_update_delete_labels_with_empty_array(self) -> None:
        """Test deleting labels by sending empty array."""
        update_data = {
            "domain": "face_recognition",
            "component": "dlib",
            "data": {"labels": []},
        }

        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth(
                "/api/v1/tune/camera_1",
                method="PUT",
                body=json.dumps(update_data),
            )

        assert response.code == 200

        # Verify labels were deleted
        with open(self.config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        camera_config = config["dlib"]["face_recognition"]["cameras"]["camera_1"]
        assert "labels" not in camera_config

    def test_update_delete_mask_with_empty_array(self) -> None:
        """Test deleting mask by sending empty array."""
        update_data = {
            "domain": "motion_detector",
            "component": "mog2",
            "data": {"mask": []},
        }

        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth(
                "/api/v1/tune/camera_1",
                method="PUT",
                body=json.dumps(update_data),
            )

        assert response.code == 200

        # Verify mask was deleted
        with open(self.config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        camera_config = config["mog2"]["motion_detector"]["cameras"]["camera_1"]
        assert "mask" not in camera_config

    def test_update_miscellaneous_fields(self) -> None:
        """Test updating miscellaneous fields."""
        update_data = {
            "domain": "object_detector",
            "component": "darknet",
            "data": {
                "fps": 10,
                "scan_on_motion_only": True,
            },
        }

        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth(
                "/api/v1/tune/camera_1",
                method="PUT",
                body=json.dumps(update_data),
            )

        assert response.code == 200

        # Verify config was updated
        with open(self.config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        camera_config = config["darknet"]["object_detector"]["cameras"]["camera_1"]
        assert camera_config["fps"] == 10
        assert camera_config["scan_on_motion_only"] is True

    def test_update_invalid_domain(self) -> None:
        """Test updating with an invalid domain."""
        update_data = {
            "domain": "invalid_domain",
            "component": "darknet",
            "data": {},
        }

        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth(
                "/api/v1/tune/camera_1",
                method="PUT",
                body=json.dumps(update_data),
            )

        assert response.code == 400
        data = json.loads(response.body)
        assert "error" in data
        assert "invalid_domain" in data["error"]

    def test_update_missing_domain(self) -> None:
        """Test updating without domain field."""
        update_data = {
            "component": "darknet",
            "data": {},
        }

        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth(
                "/api/v1/tune/camera_1",
                method="PUT",
                body=json.dumps(update_data),
            )

        assert response.code == 400
        data = json.loads(response.body)
        assert "error" in data
        assert "domain" in data["error"]

    def test_update_missing_component(self) -> None:
        """Test updating without component field."""
        update_data = {
            "domain": "object_detector",
            "data": {},
        }

        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth(
                "/api/v1/tune/camera_1",
                method="PUT",
                body=json.dumps(update_data),
            )

        assert response.code == 400
        data = json.loads(response.body)
        assert "error" in data
        assert "component" in data["error"]

    def test_update_invalid_json(self) -> None:
        """Test updating with invalid JSON."""
        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth(
                "/api/v1/tune/camera_1",
                method="PUT",
                body="invalid json",
            )

        assert response.code == 400
        data = json.loads(response.body)
        assert "error" in data
        assert "Invalid JSON" in data["error"]

    def test_update_component_not_found(self) -> None:
        """Test updating a component that doesn't exist in config."""
        update_data = {
            "domain": "object_detector",
            "component": "non_existent_component",
            "data": {"labels": []},
        }

        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth(
                "/api/v1/tune/camera_1",
                method="PUT",
                body=json.dumps(update_data),
            )

        assert response.code == 404
        data = json.loads(response.body)
        assert "error" in data

    def test_update_camera_not_found(self) -> None:
        """Test updating a camera that doesn't exist in component."""
        update_data = {
            "domain": "object_detector",
            "component": "darknet",
            "data": {"labels": []},
        }

        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth(
                "/api/v1/tune/non_existent_camera",
                method="PUT",
                body=json.dumps(update_data),
            )

        assert response.code == 404
        data = json.loads(response.body)
        assert "error" in data

    def test_get_available_labels_darknet(self) -> None:
        """Test that available_labels is populated for darknet."""
        with patch("viseron.const.CONFIG_PATH", self.config_path), patch(
            "viseron.components.webserver.api.v1.tuning.labels._load_labels_from_file",
            return_value=["person", "car", "dog", "cat"],
        ):
            response = self.fetch_with_auth("/api/v1/tune/camera_1", method="GET")

        assert response.code == 200
        data = json.loads(response.body)

        darknet = data["object_detector"]["darknet"]
        assert "available_labels" in darknet
        assert "person" in darknet["available_labels"]
        assert "car" in darknet["available_labels"]

    def test_property_order_face_recognition(self) -> None:
        """Test that labels come before mask in face_recognition config."""
        update_data = {
            "domain": "face_recognition",
            "component": "dlib",
            "data": {
                "labels": ["Test Person"],
                "mask": [
                    {
                        "coordinates": [{"x": 0, "y": 0}, {"x": 10, "y": 10}],
                    }
                ],
            },
        }

        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth(
                "/api/v1/tune/camera_1",
                method="PUT",
                body=json.dumps(update_data),
            )

        assert response.code == 200

        # Verify property order in saved YAML
        with open(self.config_path, encoding="utf-8") as f:
            yaml_content = f.read()

        # Find the camera_1 config section
        camera_section_start = yaml_content.find("camera_1:")
        labels_pos = yaml_content.find("labels:", camera_section_start)
        mask_pos = yaml_content.find("mask:", camera_section_start)

        # Labels should appear before mask in the YAML file
        assert labels_pos < mask_pos

    def test_property_order_license_plate_recognition(self) -> None:
        """Test that labels come before mask in license_plate_recognition config."""
        update_data = {
            "domain": "license_plate_recognition",
            "component": "codeprojectai",
            "data": {
                "labels": ["TEST-123"],
                "mask": [
                    {
                        "coordinates": [{"x": 0, "y": 0}, {"x": 10, "y": 10}],
                    }
                ],
            },
        }

        with patch("viseron.const.CONFIG_PATH", self.config_path):
            response = self.fetch_with_auth(
                "/api/v1/tune/camera_1",
                method="PUT",
                body=json.dumps(update_data),
            )

        assert response.code == 200

        # Verify property order in saved YAML
        with open(self.config_path, encoding="utf-8") as f:
            yaml_content = f.read()

        # Find the camera_1 config section in license_plate_recognition
        yaml_lines = yaml_content.split("\n")
        in_plate_section = False
        in_camera_section = False
        labels_line = -1
        mask_line = -1

        for i, line in enumerate(yaml_lines):
            if "license_plate_recognition:" in line:
                in_plate_section = True
            elif in_plate_section and "camera_1:" in line:
                in_camera_section = True
            elif in_camera_section:
                if "labels:" in line:
                    labels_line = i
                elif "mask:" in line:
                    mask_line = i
                elif line.strip() and not line.startswith(" " * 8):
                    # Exited camera_1 section
                    break

        # Labels should appear before mask
        if labels_line != -1 and mask_line != -1:
            assert labels_line < mask_line
