"""``blesta report`` subcommand — fetch a Blesta report."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blesta_sdk.cli.formatters import _build_cli_client

if TYPE_CHECKING:
    import argparse


def add_parser(subparsers: argparse.Action) -> None:
    """Register the ``report`` subcommand on *subparsers*.

    :param subparsers: Subparser action from the parent parser.
    """
    p = subparsers.add_parser(
        "report",
        help="Fetch a Blesta report",
        description=(
            "Call report_manager/fetchAll for a date range."
            " CSV responses are converted to JSON rows."
        ),
    )
    p.add_argument("report_type", help="Report type (e.g., package_revenue)")
    p.add_argument(
        "--start",
        required=True,
        metavar="YYYY-MM-DD",
        help="Report start date.",
    )
    p.add_argument(
        "--end",
        required=True,
        metavar="YYYY-MM-DD",
        help="Report end date.",
    )
    p.add_argument(
        "--param",
        dest="params",
        nargs="*",
        metavar="KEY=VALUE",
        help="Extra vars[] parameters as key=value pairs.",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    """Execute the ``report`` subcommand.

    :param args: Parsed CLI arguments.
    """
    from blesta_sdk.cli.formatters import parse_params, print_error, print_json

    extra_vars = parse_params(args.params)

    api = _build_cli_client()

    response = api.get_report(
        args.report_type,
        args.start,
        args.end,
        extra_vars or None,
    )

    if response.status_code != 200:
        print_error(f"Report request failed: HTTP {response.status_code}")

    if response.is_csv:
        print_json(response.csv_data or [])
    else:
        print_json(response.data)
