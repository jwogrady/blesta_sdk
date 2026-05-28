"""Compatibility shim — import from blesta_sdk.core.response instead."""

# ruff: noqa: F401
from __future__ import annotations

import json  # exposed for test patches: patch("blesta_sdk._response.json.loads")

from blesta_sdk.core.response import _UNSET, BlestaResponse
