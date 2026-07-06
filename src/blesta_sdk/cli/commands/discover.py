"""``blesta discover`` subcommand — introspect the Blesta API schema."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse


def add_parser(subparsers: argparse.Action) -> None:
    """Register the ``discover`` subcommand on *subparsers*.

    :param subparsers: Subparser action from the parent parser.
    """
    p = subparsers.add_parser(
        "discover",
        help="Introspect the Blesta API schema",
        description="List models, methods, or get a full method spec.",
    )
    dp = p.add_subparsers(dest="discover_cmd", metavar="COMMAND")
    dp.required = True

    # discover models
    dp.add_parser("models", help="List all available API models")

    # discover methods <model>
    pm = dp.add_parser("methods", help="List all methods for a model")
    pm.add_argument("model", help="Model name (e.g., Clients)")

    # discover spec <model> <method>
    ps = dp.add_parser("spec", help="Show full spec for a model/method")
    ps.add_argument("model", help="Model name (e.g., Clients)")
    ps.add_argument("method", help="Method name (e.g., getList)")

    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    """Execute the ``discover`` subcommand.

    :param args: Parsed CLI arguments.
    """
    from blesta_sdk.cli.formatters import print_json
    from blesta_sdk.discovery.registry import _get_discovery

    disco = _get_discovery()
    cmd = args.discover_cmd

    if cmd == "models":
        print_json(disco.list_models())

    elif cmd == "methods":
        try:
            print_json(disco.list_methods(args.model))
        except KeyError as exc:
            from blesta_sdk.cli.formatters import print_error

            print_error(str(exc))

    elif cmd == "spec":
        try:
            spec = disco.get_method_spec(args.model, args.method)
            print_json(
                {
                    "model": spec.model,
                    "method": spec.method,
                    "http_method": spec.http_method,
                    "category": spec.category,
                    "description": spec.description,
                    "params": spec.params,
                    "return_type": spec.return_type,
                    "return_description": spec.return_description,
                    "source": spec.source,
                    "signature": spec.signature,
                }
            )
        except KeyError as exc:
            from blesta_sdk.cli.formatters import print_error

            print_error(str(exc))
