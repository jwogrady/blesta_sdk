"""Compatibility shim — import from blesta_sdk.core.retry instead."""

# ruff: noqa: F401
from __future__ import annotations

import random  # exposed for test patches: patch("blesta_sdk._retry.random.random")

from blesta_sdk.core.retry import jitter_delay
