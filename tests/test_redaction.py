"""Tests for the shared redaction helper (_redaction.py, issues #35, #53)."""

from __future__ import annotations

from blesta_sdk._redaction import _SENSITIVE_SUFFIXES, SENSITIVE_KEYS, redact_args

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
    """SENSITIVE_KEYS must contain exactly the post-#53 narrowed set."""
    expected = {
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
    assert expected == SENSITIVE_KEYS


def test_sensitive_suffixes_defined():
    """Suffix set must include the four documented suffixes."""
    assert "_key" in _SENSITIVE_SUFFIXES
    assert "_secret" in _SENSITIVE_SUFFIXES
    assert "_password" in _SENSITIVE_SUFFIXES
    assert "_token" in _SENSITIVE_SUFFIXES


# ---------------------------------------------------------------------------
# Issue #53 — narrowed policy: explicit tests per task spec
# ---------------------------------------------------------------------------


def test_password_redacted():
    """Exact match on 'password' must be redacted."""
    assert redact_args({"password": "secret"}) == {"password": "***"}


def test_api_key_redacted():
    """Exact match on 'api_key' must be redacted."""
    assert redact_args({"api_key": "abc123"}) == {"api_key": "***"}


def test_card_number_redacted():
    """Exact match on 'card_number' must be redacted."""
    assert redact_args({"card_number": "4111111111111111"}) == {"card_number": "***"}


def test_cvv_redacted():
    """Exact match on 'cvv' must be redacted."""
    assert redact_args({"cvv": "123"}) == {"cvv": "***"}


def test_ssn_redacted():
    """ssn (new in #53) must be redacted."""
    assert redact_args({"ssn": "123-45-6789"}) == {"ssn": "***"}


def test_pin_redacted():
    """pin (new in #53) must be redacted."""
    assert redact_args({"pin": "1234"}) == {"pin": "***"}


def test_private_key_redacted():
    """private_key (new in #53) must be redacted."""
    assert redact_args({"private_key": "-----BEGIN RSA"}) == {"private_key": "***"}


def test_generic_key_preserved():
    """Bare 'key' must NOT be redacted — Blesta uses it as a record identifier."""
    result = redact_args({"key": "some-blesta-record-id"})
    assert result == {"key": "some-blesta-record-id"}


def test_generic_card_preserved():
    """Bare 'card' must NOT be redacted — Blesta uses it as a payment method name."""
    result = redact_args({"card": "visa"})
    assert result == {"card": "visa"}


def test_generic_pass_preserved():
    """Bare 'pass' must NOT be redacted — 'password'/'passwd' cover real secrets."""
    result = redact_args({"pass": "some-value"})
    assert result == {"pass": "some-value"}


def test_suffix_key_redacted():
    """Keys ending in '_key' must be redacted via suffix matching."""
    assert redact_args({"auth_key": "xyz"}) == {"auth_key": "***"}


def test_suffix_secret_redacted():
    """Keys ending in '_secret' must be redacted via suffix matching."""
    assert redact_args({"client_secret": "xyz"}) == {"client_secret": "***"}


def test_suffix_password_redacted():
    """Keys ending in '_password' must be redacted via suffix matching."""
    assert redact_args({"db_password": "hunter2"}) == {"db_password": "***"}


def test_suffix_token_redacted():
    """Keys ending in '_token' must be redacted via suffix matching."""
    assert redact_args({"auth_token": "tok123"}) == {"auth_token": "***"}


def test_nested_redaction_still_works():
    """Nested sensitive fields are still redacted after policy narrowing."""
    args = {
        "client": {
            "name": "Bob",
            "api_key": "supersecret",
            "card": "visa",
        }
    }
    result = redact_args(args)
    assert result == {
        "client": {
            "name": "Bob",
            "api_key": "***",
            "card": "visa",
        }
    }


def test_case_insensitive_redaction():
    """Matching is case-insensitive — PASSWORD, Api_Key, etc. must be redacted."""
    args = {"PASSWORD": "x", "Api_Key": "y", "Card_Number": "z", "card": "visa"}
    result = redact_args(args)
    assert result["PASSWORD"] == "***"
    assert result["Api_Key"] == "***"
    assert result["Card_Number"] == "***"
    assert result["card"] == "visa"
