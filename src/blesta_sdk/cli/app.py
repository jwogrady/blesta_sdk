"""Main entry point for the ``blesta`` CLI command.

Supports both the original flag-style syntax::

    blesta --model clients --method getList --action GET --params status=active

and the new subcommand syntax::

    blesta call clients getList --param status=active
    blesta extract clients getList --param status=active --format jsonl
    blesta report package_revenue --start 2025-01-01 --end 2025-01-31
    blesta discover models
    blesta discover methods Clients
    blesta discover spec Clients getList
"""

from __future__ import annotations

import argparse
import sys

from blesta_sdk.core.client import BlestaRequest


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser.

    :return: Configured :class:`~argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="blesta",
        description="Blesta API Command Line Interface",
    )

    # ---- Legacy top-level flags (backward compat) ----------------------
    parser.add_argument(
        "--model",
        help="[Legacy] Blesta API model (e.g., clients). Use subcommands instead.",
    )
    parser.add_argument(
        "--method",
        help="[Legacy] Blesta API method (e.g., getList). Use subcommands instead.",
    )
    parser.add_argument(
        "--action",
        type=str.upper,
        choices=["GET", "POST", "PUT", "DELETE"],
        default="GET",
        help="[Legacy] HTTP action. Use subcommands instead.",
    )
    parser.add_argument(
        "--params",
        nargs="*",
        metavar="KEY=VALUE",
        help="[Legacy] Request parameters. Use subcommands instead.",
    )
    parser.add_argument(
        "--last-request",
        action="store_true",
        help="[Legacy] Show the last API request made.",
    )

    # ---- Subcommands ----------------------------------------------------
    subparsers = parser.add_subparsers(dest="subcommand", metavar="COMMAND")

    from blesta_sdk.cli.commands.call import add_parser as add_call
    from blesta_sdk.cli.commands.discover import add_parser as add_discover
    from blesta_sdk.cli.commands.extract import add_parser as add_extract
    from blesta_sdk.cli.commands.report import add_parser as add_report

    add_call(subparsers)
    add_extract(subparsers)
    add_report(subparsers)
    add_discover(subparsers)

    return parser


def main() -> None:
    """Entry point for the ``blesta`` console script.

    Reads credentials from ``BLESTA_API_URL``, ``BLESTA_API_USER``,
    and ``BLESTA_API_KEY`` environment variables. If ``python-dotenv``
    is installed, also loads ``.env`` from the current directory.

    Set ``BLESTA_AUTH_METHOD`` to ``"header"`` to use header-based auth.
    Set ``BLESTA_ALLOW_HTTP=1`` to permit ``http://`` base URLs.
    """
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    parser = _build_parser()
    args = parser.parse_args()

    # ---- Route to subcommand -------------------------------------------
    if args.subcommand is not None:
        # Dispatch to registered subcommand handler.
        args.func(args)
        return

    # ---- Legacy flat-flag mode (--model / --method) --------------------
    if args.model or args.method:
        _run_legacy(args)
        return

    # No args at all → print help.
    parser.print_help()
    sys.exit(0)


def _run_legacy(args: argparse.Namespace) -> None:
    """Handle the legacy ``--model/--method`` syntax.

    Delegates to the original :func:`~blesta_sdk._cli.cli` implementation
    so existing callers and test patches continue to work unchanged.

    :param args: Parsed arguments from the top-level parser.
    """
    # Reconstruct sys.argv as if the legacy CLI was called directly.
    # This is the simplest way to reuse the original argument parsing
    # without duplicating credential / validation logic.
    import os

    from blesta_sdk.cli.formatters import print_error, print_json

    url = os.getenv("BLESTA_API_URL")
    user = os.getenv("BLESTA_API_USER")
    key = os.getenv("BLESTA_API_KEY")

    if not all([url, user, key]):
        print_error(
            "Missing API credentials."
            " Set BLESTA_API_URL, BLESTA_API_USER, and BLESTA_API_KEY."
        )

    if not args.model:
        print_error("--model is required in legacy mode")
    if not args.method:
        print_error("--method is required in legacy mode")

    auth_method = os.getenv("BLESTA_AUTH_METHOD", "basic").strip().lower()
    if auth_method not in ("basic", "header"):
        print_error(
            f"Invalid BLESTA_AUTH_METHOD {auth_method!r}:"
            " must be 'basic' or 'header'."
        )
    allow_http = os.getenv("BLESTA_ALLOW_HTTP", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    import logging

    log = logging.getLogger(__name__)
    params: dict[str, str] = {}
    for raw in args.params or []:
        if not raw or "=" not in raw:
            print_error(f"Invalid param '{raw}': expected key=value format")
        k, v = raw.split("=", 1)
        if not k:
            print_error(f"Invalid param '{raw}': key cannot be empty")
        if k in params:
            log.warning("Duplicate CLI param '%s' — last value wins", k)
        params[k] = v

    api = BlestaRequest(
        url,
        user,
        key,
        auth_method=auth_method,
        allow_http=allow_http,
    )
    response = api.submit(args.model, args.method, params, args.action)

    if response.status_code == 200:
        print_json(response.data)
    else:
        print_json(response.errors())

    if args.last_request:
        last_request = api.get_last_request()
        if last_request:
            print("\nLast Request URL:", last_request["url"])
            print("Last Request Parameters:", last_request["args"])
        else:
            print("No previous API request made.")

    if response.status_code != 200:
        sys.exit(1)
