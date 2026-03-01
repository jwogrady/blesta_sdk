"""Internal CLI entry point for the ``blesta`` command.

This module is not part of the public API and may change without notice.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from blesta_sdk._client import BlestaRequest


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

    url = os.getenv("BLESTA_API_URL")
    user = os.getenv("BLESTA_API_USER")
    key = os.getenv("BLESTA_API_KEY")

    if not all([url, user, key]):
        print(
            json.dumps(
                {
                    "error": "Missing API credentials."
                    " Set BLESTA_API_URL, BLESTA_API_USER, and BLESTA_API_KEY."
                },
                indent=4,
            )
        )
        sys.exit(1)

    params = dict(param.split("=", 1) for param in args.params) if args.params else {}

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


if __name__ == "__main__":
    cli()
