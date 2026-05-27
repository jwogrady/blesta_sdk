"""Shared redaction helpers for debug-safe request metadata.

This module is intentionally small and transport-agnostic so both the sync
and async clients can use the same redaction policy without importing from
one another.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

REDACTED_VALUE = "***"

SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "pass",
        "token",
        "api_key",
        "key",
        "secret",
        "card_number",
        "card",
        "cvv",
        "cvc",
        "account_number",
        "routing_number",
    }
)


def redact_args(args: Mapping[str, Any]) -> dict[str, Any]:
    """Return a redacted copy of request args.

    Sensitive keys are matched case-insensitively. Nested dictionaries and
    list/tuple payloads are redacted recursively so debug output is safe even
    when credentials or payment details are nested inside structured request
    payloads.

    The input mapping and any nested containers are not modified.

    :param args: Request args dict to redact.
    :return: New dict with sensitive values replaced by ``"***"``.
    """
    return {str(key): _redact_value(str(key), value) for key, value in args.items()}


def _redact_value(key: str, value: Any) -> Any:
    """Redact *value* when *key* is sensitive; otherwise recurse containers.

    :param key: The key associated with this value.
    :param value: The value to potentially redact.
    :return: Redacted value, recursively processed container, or original value.
    """
    if key.lower() in SENSITIVE_KEYS:
        return REDACTED_VALUE
    if isinstance(value, Mapping):
        return {str(k): _redact_value(str(k), v) for k, v in value.items()}
    if isinstance(value, tuple):
        return tuple(_redact_sequence(value))
    if isinstance(value, list):
        return _redact_sequence(value)
    return value


def _redact_sequence(values: Sequence[Any]) -> list[Any]:
    """Redact nested mappings inside a sequence.

    :param values: Sequence to walk.
    :return: New list with nested mappings recursively redacted.
    """
    result: list[Any] = []
    for item in values:
        if isinstance(item, Mapping):
            result.append({str(k): _redact_value(str(k), v) for k, v in item.items()})
        elif isinstance(item, tuple):
            result.append(tuple(_redact_sequence(item)))
        elif isinstance(item, list):
            result.append(_redact_sequence(item))
        else:
            result.append(item)
    return result
