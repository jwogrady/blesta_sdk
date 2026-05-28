"""Compatibility shim — import from blesta_sdk.core.pagination instead."""

# ruff: noqa: F401
from __future__ import annotations

from blesta_sdk.core.pagination import (
    _REPEAT_THRESHOLD,
    _WINDOW_SIZE,
    PaginationState,
)
