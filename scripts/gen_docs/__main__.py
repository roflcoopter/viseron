"""Generate docs skeleton."""
import argparse
import importlib
import json
import os
import sys
from collections.abc import Mapping

import typing_extensions
import voluptuous as vol

from viseron.config import UNSUPPORTED
from viseron.helpers.validators import CameraIdentifier, CoerceNoneToDict, Maybe, Slug
from viseron.types import SupportedDomains

from .const import (
    DOCS_CONTENTS,
    DOCS_IMPORTS,
    DOMAIN_CONTENT,
    DOMAIN_IMPORTS,
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
def convert(schema, custom_convert=None):  # noqa: C901
    """Convert a voluptuous schema to a dictionary."""
    if isinstance(schema, vol.Schema):
        schema = schema.schema

    if custom_convert:
        val = custom_convert(schema)
        if val is not UNSUPPORTED:
            return val

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

            pval = convert(value, custom_convert=custom_convert)
            if isinstance(pval, list):
                pval = {"type": "map", "value": pval}

            if not isinstance(pkey, str):
                pval["name"] = convert(key, custom_convert=custom_convert)
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
            val.append(convert(validator, custom_convert=custom_convert))
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
            val.append(convert(validator, custom_convert=custom_convert))
        options = recurse_options(val)
        return {
            "type": "select",
            "options": options,
        }

    if isinstance(schema, vol.All):
        val_list = []
        val_dict = {}
        for validator in schema.validators:
            if isinstance(validator, CoerceNoneToDict):
                continue

            _val = convert(validator, custom_convert=custom_convert)
            if isinstance(_val, list):
                for __val in _val:
                    val_list.append(__val)
            else:
                val_dict.update(_val)

        if val_list:
            return val_list
        return val_dict

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
                "options": [
                    convert(item, custom_convert=custom_convert)
                    for item in schema.container
                ],
            }
        return {
            "type": "select",
            "options": [
                convert(item, custom_convert=custom_convert)
                for item in schema.container
            ],
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

    if isinstance(schema, list):
        return {
            "type": "list",
            "values": [convert(item, custom_convert=custom_convert) for item in schema],
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
    if isinstance(schema, Slug):
        return {
            "type": "string",
        }

    if callable(schema):
        return {"type": "custom_validator", "value": "unable_to_convert"}

    raise ValueError("Unable to convert schema: {}".format(schema))
    # return {"type": "unsupported", "value": "unable_to_convert"}


def import_domain(component, domain):
    """Return if domain is supported by component."""
    try:
        return importlib.import_module(f"viseron.components.{component}.{domain}")
    except ModuleNotFoundError:
        pass
    return False


def sort_required(config):
    """Put required options first."""
    if isinstance(config, list):
        for item in config:
            sort_required(item)

    if isinstance(config, dict) and config.get("type", None) == "map":
        newlist = sorted(
            config["value"], key=lambda d: d.get("required", False), reverse=True
        )
        config["value"] = newlist
        for item in config["value"]:
            sort_required(item)


def generate_index(supported_domains):
    """Generate index.md file."""
    sorted_domains = dict(sorted(supported_domains.items()))

    docs = DOCS_IMPORTS
    for domain in sorted_domains:
        docs += DOMAIN_IMPORTS.get(domain)

    docs += DOCS_CONTENTS
    for domain in sorted_domains:
        docs += DOMAIN_CONTENT.get(domain)

    return docs


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

    supported_domains = {}
    for domain in typing_extensions.get_args(SupportedDomains):
        imported_domain = import_domain(component, domain)
        if imported_domain:
            supported_domains[domain] = imported_domain
    print(f"Found domains: {list(supported_domains.keys())}")

    if not os.path.exists(os.path.join(docs_path, "_meta.tsx")):
        print("_meta.tsx is missing, creating new from template")
        with open(
            os.path.join(docs_path, "_meta.tsx"),
            "w",
            encoding="utf-8",
        ) as data_file:
            data_file.write(
                META_CONTENTS.format(
                    component=component, tags=json.dumps(list(supported_domains.keys()))
                )
            )
    else:
        print("_meta.tsx found, will NOT overwrite")

    if not os.path.exists(os.path.join(docs_path, "index.mdx")):
        print("index.mdx is missing, creating new from template")
        docs = generate_index(supported_domains)

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
        try:
            config_module = importlib.import_module(
                f"viseron.components.{component}.config"
            )
        except ModuleNotFoundError:
            config_module = None

        custom_convert = None
        if config_module and hasattr(config_module, "custom_convert"):
            custom_convert = config_module.custom_convert

        component_config = convert(
            component_module.CONFIG_SCHEMA, custom_convert=custom_convert
        )

        for domain, domain_module in supported_domains.items():
            if hasattr(domain_module, "CONFIG_SCHEMA"):
                domain_config = convert(
                    domain_module.CONFIG_SCHEMA, custom_convert=custom_convert
                )
                for index, _domain in enumerate(component_config[0]["value"]):
                    if _domain["name"] == domain:
                        component_config[0]["value"][index]["value"] = domain_config
                        break

        sort_required(component_config)
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
        os.path.isdir("viseron")
        and os.path.isdir("viseron/components")
        and os.path.isdir("docs")
        and os.path.isdir("scripts")
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
