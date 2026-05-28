"""Compatibility shim — import from blesta_sdk.discovery.registry instead."""

# ruff: noqa: F401
from __future__ import annotations

from blesta_sdk.discovery.registry import (
    _DELETE_PREFIXES,
    _GET_PREFIXES,
    _POST_PREFIXES,
    _PUT_PREFIXES,
    BlestaDiscovery,
    MethodSpec,
    _bundled_schema_text,
    _get_discovery,
    _infer_http_method,
)
