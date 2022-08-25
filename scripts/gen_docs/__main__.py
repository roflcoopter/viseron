"""Generate docs skeleton."""
import argparse
import importlib
import json
import os
import sys
from collections.abc import Mapping

import typing_extensions
import voluptuous as vol

from viseron.helpers.validators import CameraIdentifier, CoerceNoneToDict, Maybe
from viseron.types import SupportedDomains

from .const import (
    DOCS_CONTENTS,
    DOCS_FACE_RECOGNITION_CONTENTS,
    DOCS_FACE_RECOGNITION_IMPORTS,
    DOCS_IMPORTS,
    DOCS_MOTION_DETECTOR_CONTENTS,
    DOCS_MOTION_DETECTOR_IMPORTS,
    DOCS_OBJECT_DETECTOR_CONTENTS,
    DOCS_OBJECT_DETECTOR_IMPORTS,
    META_CONTENTS,
)

TYPES_MAP = {
    int: "integer",
    str: "string",
    float: "float",
    bool: "boolean",
    list: "list",
    bytes: "bytes",
}

DOCS_PATH = "./docs/src/pages/components-explorer/components/{component}"


# This function is copied and adapted from https://github.com/home-assistant-libs/voluptuous-serialize/blob/2.4.0/voluptuous_serialize/__init__.py # pylint: disable=line-too-long
def convert(schema):  # noqa: C901
    """Convert a voluptuous schema to a dictionary."""
    if isinstance(schema, vol.Schema):
        schema = schema.schema

    if isinstance(schema, Mapping):
        val = []

        for key, value in schema.items():
            try:
                description = key.description
            except AttributeError:
                description = None

            if isinstance(key, vol.Marker):
                pkey = key.schema
            else:
                pkey = key

            pval = convert(value)
            if isinstance(pval, list):
                pval = {"type": "map", "value": pval}

            if not isinstance(pkey, str):
                pval["name"] = convert(key)
            else:
                pval["name"] = pkey
            pval["description"] = description

            if isinstance(key, (vol.Required, vol.Optional)):
                pval[key.__class__.__name__.lower()] = True

                if key.default is not vol.UNDEFINED:
                    pval["default"] = key.default()
                else:
                    pval["default"] = None
                pval["description"] = description

            val.append(pval)

        return val

    def recurse_options(options):
        _options = []
        for option in options:
            if "options" in option:
                _options += recurse_options(option["options"])
            else:
                _options.append(option)
        return _options

    if isinstance(schema, Maybe):
        val = []
        for validator in schema.validators:
            if validator is None:
                continue
            val.append(convert(validator))
        options = recurse_options(val)

        if len(options) == 1:
            return options[0]
        return {
            "type": "select",
            "options": options,
        }

    if isinstance(schema, vol.Any):
        val = []
        for validator in schema.validators:
            val.append(convert(validator))
        options = recurse_options(val)
        return {
            "type": "select",
            "options": options,
        }

    if isinstance(schema, vol.All):
        val = {}
        for validator in schema.validators:
            val.update(convert(validator))
        return val

    if isinstance(schema, (vol.Clamp, vol.Range)):
        val = {}
        if schema.min is not None:
            val["valueMin"] = schema.min
        if schema.max is not None:
            val["valueMax"] = schema.max
        return val

    if isinstance(schema, vol.Length):
        val = {}
        if schema.min is not None:
            val["lengthMin"] = schema.min
        if schema.max is not None:
            val["lengthMax"] = schema.max
        return val

    if isinstance(schema, vol.Datetime):
        return {
            "type": "datetime",
            "format": schema.format,
        }

    if isinstance(schema, vol.In):
        if isinstance(schema.container, Mapping):
            return {
                "type": "select",
                "options": [convert(item) for item in schema.container],
            }
        return {
            "type": "select",
            "options": [convert(item) for item in schema.container],
        }

    if schema in (vol.Lower, vol.Upper, vol.Capitalize, vol.Title, vol.Strip):
        return {
            schema.__name__.lower(): True,
        }

    if schema in (vol.Email, vol.Url, vol.FqdnUrl):
        return {
            "format": schema.__name__.lower(),
        }

    if isinstance(schema, vol.Coerce):
        schema = schema.type

    if isinstance(schema, CoerceNoneToDict):
        return convert(schema.schema)

    if isinstance(schema, list):
        return {
            "type": "list",
            "values": [convert(item) for item in schema],
        }

    try:
        if schema in TYPES_MAP:
            return {"type": TYPES_MAP[schema]}
    except TypeError as error:
        if "unhashable type" in str(error):
            pass
        else:
            raise error

    if isinstance(schema, (str, int, float, bool)):
        return {"type": "constant", "value": schema}

    if schema is None:
        return {"type": "none", "value": "null"}

    if isinstance(schema, CameraIdentifier):
        return {
            "type": "CAMERA_IDENTIFIER",
        }

    if callable(schema):
        return {"type": "custom_validator", "value": "unable_to_convert"}

    raise ValueError("Unable to convert schema: {}".format(schema))
    # return {"type": "unsupported", "value": "unable_to_convert"}


def import_domain(component, domain):
    """Return if domain is supported by component."""
    try:
        importlib.import_module(f"viseron.components.{component}.{domain}")
    except ModuleNotFoundError:
        return False
    return True


def import_component(component):
    """Dynamic import of component."""
    print(f"importing {component}")
    docs_path = os.path.join(DOCS_PATH.format(component=component))
    try:
        component_module = importlib.import_module(f"viseron.components.{component}")
    except ModuleNotFoundError as error:
        raise ModuleNotFoundError(f"Component {component} does not exist") from error

    if not os.path.exists(docs_path):
        print(f"Docs folder is missing, creating: {docs_path}")
        os.mkdir(docs_path)

    supported_domains = []
    for domain in typing_extensions.get_args(SupportedDomains):
        if import_domain(component, domain):
            supported_domains.append(domain)
    print(f"Found domains: {supported_domains}")

    if not os.path.exists(os.path.join(docs_path, "_meta.tsx")):
        print("_meta.tsx is missing, creating new from template")
        with open(
            os.path.join(docs_path, "_meta.tsx"),
            "w",
            encoding="utf-8",
        ) as data_file:
            data_file.write(
                META_CONTENTS.format(
                    component=component, tags=json.dumps(supported_domains)
                )
            )
    else:
        print("_meta.tsx found, will NOT overwrite")

    if not os.path.exists(os.path.join(docs_path, "index.mdx")):
        print("index.mdx is missing, creating new from template")
        docs = DOCS_IMPORTS
        if "object_detector" in supported_domains:
            docs += DOCS_OBJECT_DETECTOR_IMPORTS
        if "motion_detector" in supported_domains:
            docs += DOCS_MOTION_DETECTOR_IMPORTS
        if "face_recognition" in supported_domains:
            docs += DOCS_FACE_RECOGNITION_IMPORTS

        docs += DOCS_CONTENTS
        if "object_detector" in supported_domains:
            docs += DOCS_OBJECT_DETECTOR_CONTENTS
        if "motion_detector" in supported_domains:
            docs += DOCS_MOTION_DETECTOR_CONTENTS
        if "face_recognition" in supported_domains:
            docs += DOCS_FACE_RECOGNITION_CONTENTS

        with open(
            os.path.join(docs_path, "index.mdx"),
            "w",
            encoding="utf-8",
        ) as data_file:
            data_file.write(docs)
    else:
        print("index.mdx found, will NOT overwrite")

    component_config = {}
    if hasattr(component_module, "CONFIG_SCHEMA"):
        component_config = convert(component_module.CONFIG_SCHEMA)
        print("Writing config.json")
        with open(
            os.path.join(docs_path, "config.json"),
            "w",
            encoding="utf-8",
        ) as data_file:
            data_file.write(json.dumps(component_config, indent=4))


def main():
    """Generate docs skeleton."""
    if (
        os.path.isfile("requirements.txt")
        and os.path.isdir("viseron")
        and os.path.isdir("viseron/components")
    ):
        pass
    else:
        print("Run this from Viseron root dir")
        return 1

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--component",
        help="What component to generate doc skeleton for",
        required=True,
    )
    args = parser.parse_args()
    import_component(args.component)
    print("Done!")


if __name__ == "__main__":
    sys.exit(main())
