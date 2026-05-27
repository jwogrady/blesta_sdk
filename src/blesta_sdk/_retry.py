"""Retry helpers shared by the sync and async clients.

This module is not part of the public API and may change without notice.
"""

from __future__ import annotations

import random


def jitter_delay(attempt: int) -> float:
    """Return exponential backoff delay with ±50% jitter for *attempt*.

    Uses a half-to-full jitter strategy: the delay is between 50% and 100%
    of the base ``2 ** attempt`` seconds, which prevents thundering-herd
    retries while keeping the average close to the full exponential value.

    :param attempt: Zero-based attempt index (0 on the first retry).
    :return: Sleep duration in seconds.
    """
    base = 2**attempt
    return base * (0.5 + random.random() * 0.5)  # noqa: S311
