"""Internal CLI entry point for the ``blesta`` command.

This module is not part of the public API and may change without notice.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from blesta_sdk._client import BlestaRequest

logger = logging.getLogger(__name__)


def _json_error(message: str) -> None:
    """Print a JSON error object and exit with code 1."""
    print(json.dumps({"error": message}, indent=4))
    sys.exit(1)


def cli():
    """CLI entry point for the ``blesta`` command.

    Reads credentials from ``BLESTA_API_URL``, ``BLESTA_API_USER``,
    and ``BLESTA_API_KEY`` environment variables. If ``python-dotenv``
    is installed, also loads ``.env`` from the current directory.
    """
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(description="Blesta API Command Line Interface")
    parser.add_argument(
        "--model", required=True, help="Blesta API model (e.g., clients)"
    )
    parser.add_argument(
        "--method", required=True, help="Blesta API method (e.g., getList)"
    )
    parser.add_argument(
        "--action",
        type=str.upper,
        choices=["GET", "POST", "PUT", "DELETE"],
        default="GET",
        help="HTTP action",
    )
    parser.add_argument(
        "--params",
        nargs="*",
        help="Optional key=value pairs (e.g., id=1 status=active)",
    )
    parser.add_argument(
        "--last-request", action="store_true", help="Show the last API request made"
    )

    args = parser.parse_args()

    try:
        url = os.getenv("BLESTA_API_URL")
        user = os.getenv("BLESTA_API_USER")
        key = os.getenv("BLESTA_API_KEY")

        if not all([url, user, key]):
            _json_error(
                "Missing API credentials."
                " Set BLESTA_API_URL, BLESTA_API_USER, and BLESTA_API_KEY."
            )

        params: dict[str, str] = {}
        for raw in args.params or []:
            if not raw or "=" not in raw:
                _json_error(f"Invalid param '{raw}': expected key=value format")
            k, v = raw.split("=", 1)
            if not k:
                _json_error(f"Invalid param '{raw}': key cannot be empty")
            if k in params:
                logger.warning("Duplicate CLI param '%s' — last value wins", k)
            params[k] = v

        api = BlestaRequest(url, user, key)
        response = api.submit(args.model, args.method, params, args.action)

        if response.status_code == 200:
            print(json.dumps(response.data, indent=4))
        else:
            print(json.dumps(response.errors(), indent=4))

        if args.last_request:
            last_request = api.get_last_request()
            if last_request:
                print("\nLast Request URL:", last_request["url"])
                print("Last Request Parameters:", last_request["args"])
            else:
                print("No previous API request made.")

        if response.status_code != 200:
            sys.exit(1)
    except SystemExit:
        raise
    except Exception as exc:
        _json_error(str(exc))


if __name__ == "__main__":
    cli()
