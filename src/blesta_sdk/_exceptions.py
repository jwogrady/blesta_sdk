"""Compatibility shim — import from blesta_sdk.core.errors instead."""

# ruff: noqa: F401
from __future__ import annotations

from blesta_sdk.core.errors import (
    BlestaAPIError,
    BlestaAuthError,
    BlestaConnectionError,
    BlestaError,
    BlestaRateLimitError,
    BlestaServerError,
    PaginationError,
)
