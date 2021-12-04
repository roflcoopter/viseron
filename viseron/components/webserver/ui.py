"""UI handlers."""
import os

from viseron.components.nvr import COMPONENT as NVR_COMPONENT
from viseron.config import ViseronConfig
from viseron.const import CONFIG_PATH

from .request_handler import ViseronRequestHandler


class AboutHandler(ViseronRequestHandler):
    """Handler for about-page."""

    def get(self):
        """GET request."""
        self.render("about.html", version="maj.min.pat")


class CamerasHandler(ViseronRequestHandler):
    """Handler for cameras page."""

    def get(self):
        """GET request."""
        self.render(
            "cameras.html", nvr_list=self._vis.data.get(NVR_COMPONENT, {}).values()
        )


class IndexHandler(ViseronRequestHandler):
    """Handler for index page."""

    def get(self):
        """GET request."""
        self.render("index.html")


class RecordingsHandler(ViseronRequestHandler):
    """Handler for recordings page."""

    def get(self):
        """GET request."""
        config = ViseronConfig.config
        recordings = []
        for date in sorted(os.listdir(config.recorder.folder), reverse=True):
            if not os.path.isdir(os.path.join(config.recorder.folder, date)):
                continue
            for camera in sorted(
                os.listdir(os.path.join(config.recorder.folder, date))
            ):
                if not os.path.isdir(
                    os.path.join(config.recorder.folder, date, camera)
                ):
                    continue
                for filename in sorted(
                    os.listdir(os.path.join(config.recorder.folder, date, camera)),
                    reverse=True,
                ):
                    if not os.path.isfile(
                        os.path.join(config.recorder.folder, date, camera, filename)
                    ):
                        continue
                    rec_obj = {
                        "path": os.path.join(date, camera, filename),
                        "date": date,
                        "camera": camera,
                        "filename": filename,
                    }
                    recordings.append(rec_obj)
        self.render("recordings.html", recordings=recordings)


class SettingsHandler(ViseronRequestHandler):
    """Handler for settings-page."""

    def get(self):
        """GET request."""
        with open(CONFIG_PATH, encoding="utf-8") as fptr:
            config = fptr.read()
        self.render("settings.html", config=config)

    def post(self):
        """POST request."""
        with open(CONFIG_PATH, "w", encoding="utf-8") as fptr:
            config = fptr.write(self.get_body_argument("config"))
        with open(CONFIG_PATH, encoding="utf-8") as fptr:
            config = fptr.read()
        self.render("settings.html", config=config)
