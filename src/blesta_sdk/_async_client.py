"""Compatibility shim — import from blesta_sdk.core.async_client instead."""

# ruff: noqa: F401
from __future__ import annotations

import asyncio  # for test patches: blesta_sdk._async_client.asyncio.sleep

from blesta_sdk.core.async_client import (
    _IDEMPOTENT_METHODS,
    DEFAULT_TIMEOUT,
    AsyncBlestaRequest,
    _last_request_var,
)
