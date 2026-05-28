"""``blesta call`` subcommand — invoke a single Blesta API method."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from blesta_sdk.core.client import BlestaRequest

if TYPE_CHECKING:
    import argparse

logger = logging.getLogger(__name__)


def add_parser(subparsers: argparse.Action) -> None:
    """Register the ``call`` subcommand on *subparsers*.

    :param subparsers: Subparser action from the parent parser.
    """
    p = subparsers.add_parser(
        "call",
        help="Call a single Blesta API method",
        description="Invoke model/method and print JSON response to stdout.",
    )
    p.add_argument("model", help="Blesta API model (e.g., clients)")
    p.add_argument("method", help="Blesta API method (e.g., getList)")
    p.add_argument(
        "--action",
        type=str.upper,
        choices=["GET", "POST", "PUT", "DELETE"],
        default=None,
        help="HTTP method override. Inferred from schema if omitted.",
    )
    p.add_argument(
        "--param",
        dest="params",
        nargs="*",
        metavar="KEY=VALUE",
        help="Request parameters as key=value pairs.",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    """Execute the ``call`` subcommand.

    :param args: Parsed CLI arguments.
    """
    from blesta_sdk.cli.formatters import print_error, print_json

    url = os.getenv("BLESTA_API_URL")
    user = os.getenv("BLESTA_API_USER")
    key = os.getenv("BLESTA_API_KEY")

    if not all([url, user, key]):
        print_error(
            "Missing API credentials."
            " Set BLESTA_API_URL, BLESTA_API_USER, and BLESTA_API_KEY."
        )

    auth_method = os.getenv("BLESTA_AUTH_METHOD", "basic").strip().lower()
    allow_http = os.getenv("BLESTA_ALLOW_HTTP", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    params: dict[str, str] = {}
    for raw in args.params or []:
        if not raw or "=" not in raw:
            print_error(f"Invalid param {raw!r}: expected key=value format")
        k, v = raw.split("=", 1)
        if not k:
            print_error(f"Invalid param {raw!r}: key cannot be empty")
        if k in params:
            logger.warning("Duplicate CLI param '%s' — last value wins", k)
        params[k] = v

    api = BlestaRequest(
        url,
        user,
        key,
        auth_method=auth_method,
        allow_http=allow_http,
    )

    if args.action is not None:
        response = api.submit(args.model, args.method, params, args.action)
    else:
        response = api.call(args.model, args.method, params)

    if response.status_code == 200:
        print_json(response.data)
    else:
        print_json(response.errors())
