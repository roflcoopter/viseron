"""Tiny HTTP probe used by the container smoke tests.

This script runs *inside* the container (copied in via ``docker cp``) so the
test does not need to reach the container's published port from the host.

Usage:
    python3 /tmp/http_probe.py <url>

On success, prints the HTTP status code to stdout and exits 0.
On failure, prints ``ERR <type> <message>`` to stdout and exits 1.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request


def main() -> int:
    """Probe ``sys.argv[1]`` with a 5s timeout and print the status code."""
    if len(sys.argv) < 2:
        print("ERR Usage http_probe.py <url>")  # noqa: T201
        return 1
    url = sys.argv[1]
    try:
        request = urllib.request.Request(url, method="GET")  # noqa: S310
        response = urllib.request.urlopen(request, timeout=5)  # noqa: S310
        print(response.status)  # noqa: T201
    except urllib.error.HTTPError as exc:
        # HTTP errors still carry a status code we want to consider.
        print(exc.code)  # noqa: T201
        return 0
    except Exception as exc:  # pylint: disable=broad-except # noqa: BLE001
        print(f"ERR {type(exc).__name__} {exc}")  # noqa: T201
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
