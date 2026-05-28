"""Compatibility shim — import from blesta_sdk.core.redaction instead."""

# ruff: noqa: F401
from __future__ import annotations

from blesta_sdk.core.redaction import (
    _SENSITIVE_SUFFIXES,
    REDACTED_VALUE,
    SENSITIVE_KEYS,
    _is_sensitive,
    _redact_sequence,
    _redact_value,
    redact_args,
)
