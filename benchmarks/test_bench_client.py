"""Benchmarks for BlestaRequest — mocked network, measures SDK overhead.

Isolates the Python-side cost of URL construction, auth setup,
response wrapping, pagination logic, batch extraction, and retry loops.
Network I/O is fully mocked so results reflect SDK overhead only.

Run:
    uv run pytest benchmarks/test_bench_client.py -v --benchmark-sort=mean
"""

import json
from itertools import cycle
from unittest.mock import Mock, patch

import pytest

from benchmarks.conftest import make_json_payload
from blesta_sdk import BlestaRequest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Pre-build payloads once (avoid re-serializing in every iteration)
_PAGE_25 = make_json_payload(25)
_PAGE_200 = make_json_payload(200)
_PAGE_1 = make_json_payload(1)
_EMPTY = json.dumps({"response": []})
_PAGE_EMPTY_500 = json.dumps({"response": []})
_CSV_REPORT = "Package,Revenue\nPkg1,100\nPkg2,200"


def _cycling_mock(pattern: list[tuple[str, int]]) -> Mock:
    """Return a Mock whose side_effect cycles through (text, status) pairs."""
    mocks = [Mock(text=t, status_code=s) for t, s in pattern]
    return Mock(side_effect=cycle(mocks))


# ---------------------------------------------------------------------------
# Single request overhead
# ---------------------------------------------------------------------------


class TestSubmitOverhead:
    """Measure per-request SDK overhead (URL build + response wrap)."""

    def test_get_overhead(self, benchmark):
        api = BlestaRequest("https://test.example.com/api", "u", "k")
        mock = Mock(return_value=Mock(text=_PAGE_25, status_code=200))
        with patch.object(api.session, "get", mock):
            benchmark(api.get, "clients", "getList", {"status": "active"})

    def test_post_overhead(self, benchmark):
        api = BlestaRequest("https://test.example.com/api", "u", "k")
        mock = Mock(return_value=Mock(text=_PAGE_1, status_code=200))
        with patch.object(api.session, "post", mock):
            benchmark(
                api.post,
                "clients",
                "create",
                {"firstname": "John", "lastname": "Doe"},
            )

    def test_submit_url_construction(self, benchmark):
        """Isolate URL construction cost (urljoin + string formatting)."""
        from urllib.parse import urljoin

        base = "https://test.example.com/api/"
        benchmark(urljoin, base, "clients/getList.json")


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class TestPagination:
    """Measure pagination loop overhead with mocked pages."""

    @pytest.mark.parametrize("pages", [5, 20, 50], ids=["5pg", "20pg", "50pg"])
    def test_get_all(self, benchmark, pages):
        pattern = [(_PAGE_25, 200)] * pages + [(_EMPTY, 200)]
        api = BlestaRequest("https://test.example.com/api", "u", "k")
        mock = _cycling_mock(pattern)
        with patch.object(api.session, "get", mock):
            benchmark(api.get_all, "clients", "getList")

    def test_iter_all_consumed(self, benchmark):
        """iter_all consumed into list — should match get_all overhead."""
        pattern = [(_PAGE_25, 200)] * 10 + [(_EMPTY, 200)]
        api = BlestaRequest("https://test.example.com/api", "u", "k")
        mock = _cycling_mock(pattern)
        with patch.object(api.session, "get", mock):
            benchmark(lambda: list(api.iter_all("clients", "getList")))

    def test_pagination_large_pages(self, benchmark):
        """Fewer pages with more items — tests list extension overhead."""
        pattern = [(_PAGE_200, 200)] * 5 + [(_EMPTY, 200)]
        api = BlestaRequest("https://test.example.com/api", "u", "k")
        mock = _cycling_mock(pattern)
        with patch.object(api.session, "get", mock):
            benchmark(api.get_all, "clients", "getList")


# ---------------------------------------------------------------------------
# Batch extraction
# ---------------------------------------------------------------------------


class TestExtract:
    """Measure extract() with varying target counts."""

    @pytest.mark.parametrize("targets", [1, 3, 5, 10], ids=["1t", "3t", "5t", "10t"])
    def test_extract_targets(self, benchmark, targets):
        # Each target: 3 data pages + 1 empty sentinel = 4 responses
        single = [(_PAGE_25, 200)] * 3 + [(_EMPTY, 200)]
        pattern = single * targets
        api = BlestaRequest("https://test.example.com/api", "u", "k")
        mock = _cycling_mock(pattern)
        target_list = [(f"model{i}", "getList") for i in range(targets)]
        with patch.object(api.session, "get", mock):
            benchmark(api.extract, target_list)


# ---------------------------------------------------------------------------
# Count helper
# ---------------------------------------------------------------------------


class TestCount:
    """Measure count() overhead."""

    def test_count_overhead(self, benchmark):
        api = BlestaRequest("https://test.example.com/api", "u", "k")
        response = Mock(text=json.dumps({"response": 22376}), status_code=200)
        mock = Mock(return_value=response)
        with patch.object(api.session, "get", mock):
            benchmark(api.count, "transactions")


# ---------------------------------------------------------------------------
# Retry overhead
# ---------------------------------------------------------------------------


class TestRetry:
    """Measure retry loop overhead (time.sleep is mocked out)."""

    @patch("blesta_sdk._client.time.sleep")
    def test_retry_success_after_2(self, mock_sleep, benchmark):
        pattern = [(_PAGE_EMPTY_500, 500), (_PAGE_EMPTY_500, 502), (_PAGE_25, 200)]
        api = BlestaRequest("https://test.example.com/api", "u", "k", max_retries=3)
        mock = _cycling_mock(pattern)
        with patch.object(api.session, "get", mock):
            benchmark(api.get, "clients", "getList")

    @patch("blesta_sdk._client.time.sleep")
    def test_retry_all_fail(self, mock_sleep, benchmark):
        api = BlestaRequest("https://test.example.com/api", "u", "k", max_retries=3)
        mock = Mock(return_value=Mock(text=_PAGE_EMPTY_500, status_code=500))
        with patch.object(api.session, "get", mock):
            benchmark(api.get, "clients", "getList")

    def test_no_retry_baseline(self, benchmark):
        """Baseline: max_retries=0, no retry overhead."""
        api = BlestaRequest("https://test.example.com/api", "u", "k")
        mock = Mock(return_value=Mock(text=_PAGE_25, status_code=200))
        with patch.object(api.session, "get", mock):
            benchmark(api.get, "clients", "getList")


# ---------------------------------------------------------------------------
# Report series
# ---------------------------------------------------------------------------


class TestReportSeries:
    """Measure get_report_series with mocked monthly reports."""

    @pytest.mark.parametrize("months", [3, 6, 12], ids=["3mo", "6mo", "12mo"])
    def test_report_series(self, benchmark, months):
        api = BlestaRequest("https://test.example.com/api", "u", "k")
        mock = Mock(return_value=Mock(text=_CSV_REPORT, status_code=200))
        end_map = {3: "2025-03", 6: "2025-06", 12: "2025-12"}
        with patch.object(api.session, "get", mock):
            benchmark(
                api.get_report_series,
                "package_revenue",
                "2025-01",
                end_map[months],
            )
