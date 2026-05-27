"""Shared redaction helpers for debug-safe request metadata.

This module is intentionally small and transport-agnostic so both the sync
and async clients can use the same redaction policy without importing from
one another.

Redaction policy (issue #53 — narrowed from over-broad original):
- Exact matches for clearly sensitive field names.
- Suffix matches for keys ending in ``_key``, ``_secret``, ``_password``,
  or ``_token`` so compound field names (e.g. ``auth_token``, ``private_key``)
  are covered automatically.
- Generic bare words ``key``, ``card``, and ``pass`` were removed because
  Blesta uses them as non-secret identifiers (record keys, payment method
  type names, etc.).  The suffix ``_key`` still catches ``api_key`` and
  ``private_key`` via the suffix rule.
- ``token`` is retained as an exact match: Blesta auth/session tokens are
  secrets, and the suffix ``_token`` would not cover the bare form used in
  legacy Blesta API responses.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

REDACTED_VALUE = "***"

# Exact-match sensitive field names (case-insensitive comparison applied at
# call time).  Bare generic words like ``key``, ``card``, and ``pass`` are
# intentionally absent — they match too many legitimate Blesta field names.
SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "token",
        "api_key",
        "secret",
        "private_key",
        "card_number",
        "cvv",
        "cvc",
        "account_number",
        "routing_number",
        "ssn",
        "pin",
    }
)

# Key suffixes that indicate sensitivity regardless of prefix.
# A field named ``auth_token``, ``db_password``, or ``client_secret`` will be
# redacted even if it does not appear in SENSITIVE_KEYS above.
_SENSITIVE_SUFFIXES = (
    "_key",
    "_secret",
    "_password",
    "_token",
)


def _is_sensitive(key: str) -> bool:
    """Return True when *key* matches a sensitive field name or suffix.

    :param key: Field name to evaluate (already lowercased by callers).
    :return: Whether the field should be redacted.
    """
    if key in SENSITIVE_KEYS:
        return True
    return any(key.endswith(suffix) for suffix in _SENSITIVE_SUFFIXES)


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
    if _is_sensitive(key.lower()):
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
