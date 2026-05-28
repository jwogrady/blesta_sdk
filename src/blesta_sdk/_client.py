"""Compatibility shim — import from blesta_sdk.core.client instead."""

# ruff: noqa: F401
from __future__ import annotations

import time  # exposed for test patches: patch("blesta_sdk._client.time.sleep")

from blesta_sdk.core.client import (
    _IDEMPOTENT_METHODS,
    DEFAULT_TIMEOUT,
    BlestaRequest,
)
