"""``blesta extract`` subcommand — paginate and dump all records."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from blesta_sdk.cli.formatters import _build_cli_client

if TYPE_CHECKING:
    import argparse

logger = logging.getLogger(__name__)

_FORMATS = ("json", "jsonl", "csv")


def add_parser(subparsers: argparse.Action) -> None:
    """Register the ``extract`` subcommand on *subparsers*.

    :param subparsers: Subparser action from the parent parser.
    """
    p = subparsers.add_parser(
        "extract",
        help="Fetch all pages from a list endpoint",
        description=(
            "Paginate a Blesta list method and output all records."
            " Defaults to JSON output."
        ),
    )
    p.add_argument("model", help="Blesta API model (e.g., clients)")
    p.add_argument("method", help="Blesta API method (e.g., getList)")
    p.add_argument(
        "--param",
        dest="params",
        nargs="*",
        metavar="KEY=VALUE",
        help="Request parameters as key=value pairs.",
    )
    p.add_argument(
        "--format",
        dest="output_format",
        choices=_FORMATS,
        default="json",
        help="Output format: json (default), jsonl, or csv.",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    """Execute the ``extract`` subcommand.

    :param args: Parsed CLI arguments.
    """
    from blesta_sdk.cli.formatters import (
        parse_params,
        print_csv,
        print_json,
        print_jsonl,
    )

    params = parse_params(args.params)

    api = _build_cli_client()

    rows = api.get_all(args.model, args.method, params or None)

    fmt = getattr(args, "output_format", "json")
    if fmt == "jsonl":
        print_jsonl(rows)
    elif fmt == "csv":
        if rows and isinstance(rows[0], dict):
            print_csv(rows)
        else:
            print_json(rows)
    else:
        print_json(rows)
