"""Output formatters and CLI client helper for the Blesta CLI."""

from __future__ import annotations

import json
import os
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from blesta_sdk.core.client import BlestaRequest

_TRUTHY_ENV = {"1", "true", "yes", "on"}


def _build_cli_client() -> BlestaRequest:
    """Create a :class:`~blesta_sdk.core.client.BlestaRequest` from CLI env vars.

    Reads ``BLESTA_API_URL``, ``BLESTA_API_USER``, ``BLESTA_API_KEY``,
    ``BLESTA_AUTH_METHOD`` (default ``"basic"``), and ``BLESTA_ALLOW_HTTP``
    from the environment and returns a configured client.

    Calls :func:`print_error` (which exits) if any required credential is
    missing or if ``BLESTA_AUTH_METHOD`` is not ``"basic"`` or ``"header"``.

    :return: Configured :class:`~blesta_sdk.core.client.BlestaRequest`.
    """
    from blesta_sdk.core.client import BlestaRequest

    url = os.getenv("BLESTA_API_URL")
    user = os.getenv("BLESTA_API_USER")
    key = os.getenv("BLESTA_API_KEY")
    if not all([url, user, key]):
        print_error(
            "Missing API credentials."
            " Set BLESTA_API_URL, BLESTA_API_USER, and BLESTA_API_KEY."
        )
    auth_method = os.getenv("BLESTA_AUTH_METHOD", "basic").strip().lower()
    if auth_method not in ("basic", "header"):
        print_error(
            f"Invalid BLESTA_AUTH_METHOD {auth_method!r}:"
            " must be 'basic' or 'header'."
        )
    allow_http = os.getenv("BLESTA_ALLOW_HTTP", "").strip().lower() in _TRUTHY_ENV
    return BlestaRequest(  # type: ignore[arg-type]
        url,
        user,
        key,
        auth_method=auth_method,  # type: ignore[arg-type]
        allow_http=allow_http,
    )


def print_json(data: Any, *, indent: int = 4) -> None:
    """Print *data* as indented JSON to stdout.

    :param data: JSON-serialisable value.
    :param indent: Indentation level.
    """
    print(json.dumps(data, indent=indent))


def print_jsonl(rows: list[Any]) -> None:
    """Print each item in *rows* as a separate JSON line to stdout.

    :param rows: List of JSON-serialisable values.
    """
    for row in rows:
        print(json.dumps(row))


def print_csv(rows: list[dict[str, Any]]) -> None:
    """Print *rows* as CSV to stdout.

    The first row's keys become the header.  Rows with missing keys
    receive empty strings.

    :param rows: List of dicts.
    """
    import csv
    import io

    if not rows:
        return
    fieldnames = list(rows[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=fieldnames,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    print(buf.getvalue(), end="")


def print_error(message: str, *, exit_code: int = 1) -> None:
    """Print a JSON error object to stdout and exit.

    :param message: Error description.
    :param exit_code: Process exit code.
    """
    print(json.dumps({"error": message}, indent=4))
    sys.exit(exit_code)
