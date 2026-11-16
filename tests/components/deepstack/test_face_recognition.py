"""Tests for the deepstack face_recognition component."""

from unittest.mock import patch

from viseron.components.deepstack.face_recognition import DeepstackFace


def _mock_post():
    """Return a patched requests.post with a 200 JSON response."""
    return patch("viseron.components.deepstack.face_recognition.requests.post")


class TestPostRequest:
    """Tests for DeepstackFace.post_request."""

    def test_default_data_dict_is_not_mutated(self):
        """Test that the function-level default dict stays empty.

        `data: dict = {}` created one dict shared by every call that omits
        `data`, and each call wrote its api_key into it.
        """
        with _mock_post() as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {"success": True}
            DeepstackFace.post_request("http://deepstack", api_key="k1")

        default = DeepstackFace.post_request.__defaults__[-1]
        assert not isinstance(default, dict), (
            "post_request must not use a mutable dict default"
        )

    def test_caller_data_is_not_mutated(self):
        """Test that a caller-provided data dict is not modified."""
        data = {"userid": "alice"}
        with _mock_post() as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {"success": True}
            DeepstackFace.post_request("http://deepstack", api_key="k1", data=data)
        assert data == {"userid": "alice"}

    def test_api_key_is_sent(self):
        """Test that the api key is part of the posted data."""
        with _mock_post() as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {"success": True}
            DeepstackFace.post_request("http://deepstack", api_key="k1")
        assert post.call_args.kwargs["data"] == {"api_key": "k1"}
