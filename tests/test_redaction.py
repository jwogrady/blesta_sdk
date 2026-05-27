"""Tests for the shared redaction helper (_redaction.py, issue #35)."""

from __future__ import annotations

from blesta_sdk._redaction import SENSITIVE_KEYS, redact_args

# ---------------------------------------------------------------------------
# Top-level key redaction
# ---------------------------------------------------------------------------


def test_redact_args_redacts_top_level_sensitive_keys():
    args = {
        "username": "alice",
        "password": "secret",
        "api_key": "abc123",
        "card_number": "4111111111111111",
    }
    result = redact_args(args)
    assert result == {
        "username": "alice",
        "password": "***",
        "api_key": "***",
        "card_number": "***",
    }
    # Original payload is not modified.
    assert args["password"] == "secret"
    assert args["api_key"] == "abc123"


def test_redact_args_passes_through_non_sensitive_keys():
    args = {"client_id": 42, "status": "active", "page": 1}
    assert redact_args(args) == {"client_id": 42, "status": "active", "page": 1}


def test_redact_args_empty_dict():
    assert redact_args({}) == {}


def test_redact_args_falsy_non_sensitive_values_pass_through():
    """Falsy values (0, False, '') for non-sensitive keys must not be dropped."""
    args = {"page": 0, "enabled": False, "note": ""}
    assert redact_args(args) == {"page": 0, "enabled": False, "note": ""}


# ---------------------------------------------------------------------------
# Case-insensitive matching
# ---------------------------------------------------------------------------


def test_redact_args_is_case_insensitive():
    args = {
        "Password": "secret",
        "API_KEY": "abc",
        "Card_Number": "4111",
    }
    assert redact_args(args) == {
        "Password": "***",
        "API_KEY": "***",
        "Card_Number": "***",
    }


# ---------------------------------------------------------------------------
# Nested dict redaction
# ---------------------------------------------------------------------------


def test_redact_args_redacts_nested_dicts():
    args = {
        "client": {
            "name": "Alice",
            "password": "secret",
        },
    }
    result = redact_args(args)
    assert result == {
        "client": {
            "name": "Alice",
            "password": "***",
        },
    }
    # Original not mutated.
    assert args["client"]["password"] == "secret"


def test_redact_args_redacts_nested_lists_of_dicts():
    args = {
        "payment_accounts": [
            {
                "card_number": "4111111111111111",
                "cvv": "123",
                "label": "primary",
            }
        ],
    }
    result = redact_args(args)
    assert result == {
        "payment_accounts": [
            {
                "card_number": "***",
                "cvv": "***",
                "label": "primary",
            }
        ],
    }
    assert args["payment_accounts"][0]["card_number"] == "4111111111111111"


def test_redact_args_redacts_deeply_nested_structures():
    args = {
        "client": {
            "name": "Alice",
            "password": "secret",
        },
        "payment_accounts": [
            {
                "card_number": "4111111111111111",
                "cvv": "123",
                "label": "primary",
            }
        ],
        "metadata": [
            {
                "token": "nested-token",
            }
        ],
    }
    assert redact_args(args) == {
        "client": {
            "name": "Alice",
            "password": "***",
        },
        "payment_accounts": [
            {
                "card_number": "***",
                "cvv": "***",
                "label": "primary",
            }
        ],
        "metadata": [
            {
                "token": "***",
            }
        ],
    }


def test_redact_args_redacts_nested_tuples():
    args = {
        "pairs": ({"password": "s3cr3t", "user": "alice"},),
    }
    result = redact_args(args)
    assert result["pairs"] == ({"password": "***", "user": "alice"},)


def test_redact_args_leaves_plain_list_values_intact():
    """Non-mapping items inside lists are returned unchanged."""
    args = {"ids": [1, 2, 3], "tags": ["billing", "active"]}
    assert redact_args(args) == {"ids": [1, 2, 3], "tags": ["billing", "active"]}


def test_redact_args_nested_tuple_inside_sequence():
    """Tuple nested inside a list is recursed (line 79 of _redaction.py)."""
    args = {"items": [({"password": "s3cr3t"},)]}
    result = redact_args(args)
    assert result == {"items": [({"password": "***"},)]}


def test_redact_args_nested_list_inside_list():
    """List nested inside a list is recursed (line 81 of _redaction.py)."""
    args = {"groups": [[{"token": "abc"}, {"user": "alice"}]]}
    result = redact_args(args)
    assert result == {"groups": [[{"token": "***"}, {"user": "alice"}]]}


# ---------------------------------------------------------------------------
# Sensitive key inventory
# ---------------------------------------------------------------------------


def test_sensitive_keys_contains_expected_entries():
    expected = {
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
    assert expected == SENSITIVE_KEYS
