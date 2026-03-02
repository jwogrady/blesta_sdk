"""Regression tests for BlestaResponse parsing edge cases.

Covers adversarial inputs that previously caused AttributeError,
TypeError, or silent misclassification.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from blesta_sdk import BlestaResponse
from blesta_sdk._response import _UNSET


def make_response(body: str | None, status: int) -> BlestaResponse:
    """Shortcut to construct a BlestaResponse for testing."""
    return BlestaResponse(body, status)


# --- Case 1: Empty body with 200 ---


class TestEmptyBody200:
    def test_errors_reports_empty_body(self):
        r = make_response("", 200)
        err = r.errors()
        assert err is not None
        assert "Empty response body" in err["error"]

    def test_data_is_none(self):
        r = make_response("", 200)
        assert r.data is None

    def test_not_csv(self):
        r = make_response("", 200)
        assert r.is_csv is False

    def test_not_json(self):
        r = make_response("", 200)
        assert r.is_json is False

    def test_to_dataframe_raises(self):
        r = make_response("", 200)
        with pytest.raises(ValueError):
            r.to_dataframe()


# --- Case 2: HTML error page with 500 ---


class TestHtmlError500:
    HTML = (
        "<html>\n"
        '<head><meta name="author" content="Foo, Inc."></head>\n'
        "<body><h1>500 Internal Server Error</h1></body>\n"
        "</html>"
    )

    def test_not_csv(self):
        r = make_response(self.HTML, 500)
        assert r.is_csv is False

    def test_errors_contains_http_500(self):
        r = make_response(self.HTML, 500)
        err = r.errors()
        assert err is not None
        assert "HTTP 500" in err["error"]

    def test_no_crash_on_all_properties(self):
        r = make_response(self.HTML, 500)
        _ = r.data
        _ = r.is_json
        _ = r.is_csv
        _ = r.errors()
        _ = r.raw


# --- Case 3: text/plain error body with 401 ---


class TestPlainTextError401:
    def test_not_csv(self):
        r = make_response("Unauthorized", 401)
        assert r.is_csv is False

    def test_errors_contains_http_401(self):
        r = make_response("Unauthorized", 401)
        err = r.errors()
        assert err is not None
        assert "HTTP 401" in err["error"]

    def test_multiline_with_comma_not_csv(self):
        """Multi-line text/plain with comma must not be classified as CSV."""
        r = make_response("Error, something happened\nContact support", 401)
        assert r.is_csv is False

    def test_no_crash(self):
        r = make_response("Unauthorized", 401)
        _ = r.data
        _ = r.errors()


# --- Case 4: Malformed JSON with 200 ---


class TestMalformedJson200:
    BODY = '{"response": [1,2,3'

    def test_errors_contains_invalid_json(self):
        r = make_response(self.BODY, 200)
        err = r.errors()
        assert err is not None
        assert "Invalid JSON response:" in err["error"]

    def test_error_includes_decode_detail(self):
        r = make_response(self.BODY, 200)
        err = r.errors()
        # The colon separates the prefix from the JSONDecodeError message.
        parts = err["error"].split(":", 1)
        assert len(parts) == 2
        assert len(parts[1].strip()) > 0

    def test_no_crash(self):
        r = make_response(self.BODY, 200)
        _ = r.data
        _ = r.is_json
        _ = r.is_csv


# --- Case 5: JSON string containing commas with 200 ---


class TestJsonString200:
    BODY = '"hello, world"'

    def test_is_json(self):
        r = make_response(self.BODY, 200)
        assert r.is_json is True

    def test_data_returns_string(self):
        r = make_response(self.BODY, 200)
        assert r.data == "hello, world"

    def test_errors_is_none(self):
        r = make_response(self.BODY, 200)
        assert r.errors() is None

    def test_to_dataframe_raises_for_str(self):
        r = make_response(self.BODY, 200)
        with pytest.raises(ValueError, match="Cannot convert response of type str"):
            r.to_dataframe()


# --- Case 6: CSV with semicolon delimiter with 200 ---


class TestSemicolonCsv200:
    BODY = "a;b;c\n1;2;3"

    def test_not_csv(self):
        r = make_response(self.BODY, 200)
        assert r.is_csv is False

    def test_errors_is_not_none(self):
        r = make_response(self.BODY, 200)
        err = r.errors()
        assert err is not None

    def test_no_crash(self):
        r = make_response(self.BODY, 200)
        _ = r.data
        _ = r.errors()
        _ = r.is_csv


# --- Case 7: CSV-like JSON header (weird but should not crash) ---


class TestCsvLikeJsonHeader:
    BODY = '{"id","name"}\n{"1","test"}'

    def test_is_csv(self):
        r = make_response(self.BODY, 200)
        assert r.is_csv is True

    def test_to_dataframe_returns_nonempty(self):
        r = make_response(self.BODY, 200)
        df = r.to_dataframe()
        assert len(df) > 0

    def test_errors_is_none(self):
        r = make_response(self.BODY, 200)
        assert r.errors() is None


# --- Case 8: JSON array of strings with commas with 200 ---


class TestJsonArray200:
    BODY = '["hello, world", "foo, bar"]'

    def test_data_returns_list(self):
        r = make_response(self.BODY, 200)
        assert r.data == ["hello, world", "foo, bar"]

    def test_is_json(self):
        r = make_response(self.BODY, 200)
        assert r.is_json is True

    def test_errors_is_none(self):
        r = make_response(self.BODY, 200)
        assert r.errors() is None

    def test_no_crash(self):
        r = make_response(self.BODY, 200)
        _ = r.data
        _ = r.errors()
        _ = r.is_csv


# --- Case 9: Body is literal "null" with 200 ---


class TestNullBody200:
    BODY = "null"

    def test_data_is_none(self):
        r = make_response(self.BODY, 200)
        assert r.data is None

    def test_errors_is_none(self):
        r = make_response(self.BODY, 200)
        assert r.errors() is None

    def test_is_json(self):
        r = make_response(self.BODY, 200)
        assert r.is_json is True

    def test_caching_does_not_reparse(self):
        """Accessing data multiple times must not re-invoke json.loads."""
        r = make_response(self.BODY, 200)
        # Prime the cache.
        _ = r.data
        # Confirm _parsed is no longer the sentinel.
        assert r._parsed is not _UNSET
        # Patch json.loads to detect any further calls.
        with patch("blesta_sdk._response.json.loads") as mock_loads:
            _ = r.data
            _ = r.data
            mock_loads.assert_not_called()


# --- Case 10: Body is "{}" with 200 ---


class TestEmptyJsonObject200:
    BODY = "{}"

    def test_data_is_none(self):
        r = make_response(self.BODY, 200)
        assert r.data is None

    def test_errors_is_none(self):
        r = make_response(self.BODY, 200)
        assert r.errors() is None

    def test_to_dataframe_raises(self):
        r = make_response(self.BODY, 200)
        with pytest.raises(ValueError, match="data is None"):
            r.to_dataframe()


# --- Invariant: _format_response always returns dict ---


class TestFormatResponseInvariant:
    @pytest.mark.parametrize(
        "body",
        [
            "",
            "null",
            '"x"',
            "123",
            "true",
            '["a"]',
            "{}",
            '{"response": 1}',
            None,
        ],
    )
    def test_always_returns_dict(self, body):
        r = make_response(body, 200)
        result = r._format_response()
        assert isinstance(result, dict)

    @pytest.mark.parametrize(
        "body",
        [
            "",
            "null",
            '"x"',
            "123",
            "true",
            '["a"]',
            "{}",
            '{"response": 1}',
            None,
        ],
    )
    def test_no_attribute_error_on_data(self, body):
        r = make_response(body, 200)
        # Must not raise AttributeError.
        _ = r.data

    @pytest.mark.parametrize(
        "body",
        [
            "",
            "null",
            '"x"',
            "123",
            "true",
            '["a"]',
            "{}",
            '{"response": 1}',
            None,
        ],
    )
    def test_no_type_error_on_errors(self, body):
        r = make_response(body, 200)
        # Must not raise TypeError.
        _ = r.errors()

    @pytest.mark.parametrize(
        "body",
        [
            "",
            "null",
            '"x"',
            "123",
            "true",
            '["a"]',
            "{}",
            '{"response": 1}',
            None,
        ],
    )
    def test_no_crash_on_non_200_errors(self, body):
        """errors() must not crash for any body when status is non-200."""
        r = make_response(body, 500)
        err = r.errors()
        assert err is not None
