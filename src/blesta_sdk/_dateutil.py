"""Internal date range utilities for time-series report iteration.

This module is not part of the public API and may change without notice.
"""

from __future__ import annotations

import calendar
from datetime import date


def _month_boundaries(start_month: str, end_month: str) -> list[tuple[str, str, str]]:
    """Generate (first_day, last_day, period) for each month in range.

    :param start_month: Start month as "YYYY-MM" (e.g., "2020-01").
    :param end_month: End month as "YYYY-MM" (e.g., "2026-12"), inclusive.
    :return: List of tuples ("YYYY-MM-DD", "YYYY-MM-DD", "YYYY-MM").
    :raises ValueError: If start_month > end_month or format is invalid.
    """
    try:
        start_year, start_mon = (int(x) for x in start_month.split("-"))
        end_year, end_mon = (int(x) for x in end_month.split("-"))
    except (ValueError, AttributeError) as err:
        raise ValueError(
            f"Invalid month format: expected 'YYYY-MM', "
            f"got {start_month!r} / {end_month!r}"
        ) from err

    start = date(start_year, start_mon, 1)
    end = date(end_year, end_mon, 1)
    if start > end:
        raise ValueError(
            f"start_month {start_month!r} is after end_month {end_month!r}"
        )

    result: list[tuple[str, str, str]] = []
    current = start
    while current <= end:
        y, m = current.year, current.month
        last_day = calendar.monthrange(y, m)[1]
        first = date(y, m, 1).isoformat()
        last = date(y, m, last_day).isoformat()
        period = f"{y:04d}-{m:02d}"
        result.append((first, last, period))
        current = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
    return result
