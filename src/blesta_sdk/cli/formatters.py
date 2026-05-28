"""Output formatters for the Blesta CLI."""

from __future__ import annotations

import json
import sys
from typing import Any


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
