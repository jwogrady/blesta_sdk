"""Benchmarks for AsyncBlestaRequest — mocked network, measures SDK overhead.

Mirrors test_bench_client.py for the async client. Uses asyncio.run()
inside benchmark calls since pytest-benchmark doesn't natively support
async functions.

Run:
    uv run pytest benchmarks/test_bench_async_client.py -v --benchmark-sort=mean
"""

import asyncio
import json
from itertools import cycle
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from benchmarks.conftest import make_json_payload
from blesta_sdk import AsyncBlestaRequest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PAGE_25 = make_json_payload(25)
_PAGE_200 = make_json_payload(200)
_PAGE_1 = make_json_payload(1)
_EMPTY = json.dumps({"response": []})
_PAGE_EMPTY_500 = json.dumps({"response": []})
_CSV_REPORT = "Package,Revenue\nPkg1,100\nPkg2,200"


def _make_httpx_response(text: str, status_code: int) -> httpx.Response:
    """Build a real httpx.Response with the given text and status."""
    resp = httpx.Response(status_code, text=text)
    return resp


def _cycling_async_mock(pattern: list[tuple[str, int]]) -> AsyncMock:
    """Return an AsyncMock whose side_effect cycles through (text, status) pairs."""
    responses = [_make_httpx_response(t, s) for t, s in pattern]
    return AsyncMock(side_effect=cycle(responses))


# ---------------------------------------------------------------------------
# Single request overhead
# ---------------------------------------------------------------------------


class TestAsyncSubmitOverhead:
    """Measure per-request SDK overhead (URL build + response wrap)."""

    def test_get_overhead(self, benchmark):
        def run():
            api = AsyncBlestaRequest("https://test.example.com/api", "u", "k")
            mock = AsyncMock(return_value=_make_httpx_response(_PAGE_25, 200))
            with patch.object(api.client, "get", mock):
                return asyncio.run(api.get("transactions", "getList"))

        benchmark(run)

    def test_post_overhead(self, benchmark):
        def run():
            api = AsyncBlestaRequest("https://test.example.com/api", "u", "k")
            mock = AsyncMock(return_value=_make_httpx_response(_PAGE_1, 200))
            with patch.object(api.client, "post", mock):
                return asyncio.run(
                    api.post("transactions", "create", {"amount": "100.00"})
                )

        benchmark(run)


# ---------------------------------------------------------------------------
# Pagination — get_all("transactions", "getList")
# ---------------------------------------------------------------------------


class TestAsyncPagination:
    """Measure async pagination loop overhead with mocked pages."""

    @pytest.mark.parametrize("pages", [5, 20, 50], ids=["5pg", "20pg", "50pg"])
    def test_get_all(self, benchmark, pages):
        pattern = [(_PAGE_25, 200)] * pages + [(_EMPTY, 200)]

        def run():
            api = AsyncBlestaRequest("https://test.example.com/api", "u", "k")
            mock = _cycling_async_mock(pattern)
            with patch.object(api.client, "get", mock):
                return asyncio.run(api.get_all("transactions", "getList"))

        benchmark(run)

    def test_iter_all_consumed(self, benchmark):
        """iter_all consumed into list — should match get_all overhead."""
        pattern = [(_PAGE_25, 200)] * 10 + [(_EMPTY, 200)]

        def run():
            api = AsyncBlestaRequest("https://test.example.com/api", "u", "k")
            mock = _cycling_async_mock(pattern)

            async def consume():
                with patch.object(api.client, "get", mock):
                    return [
                        item async for item in api.iter_all("transactions", "getList")
                    ]

            return asyncio.run(consume())

        benchmark(run)

    def test_pagination_large_pages(self, benchmark):
        """Fewer pages with more items — tests list extension overhead."""
        pattern = [(_PAGE_200, 200)] * 5 + [(_EMPTY, 200)]

        def run():
            api = AsyncBlestaRequest("https://test.example.com/api", "u", "k")
            mock = _cycling_async_mock(pattern)
            with patch.object(api.client, "get", mock):
                return asyncio.run(api.get_all("transactions", "getList"))

        benchmark(run)


# ---------------------------------------------------------------------------
# Batch extraction — extract() with asyncio.gather
# ---------------------------------------------------------------------------


class TestAsyncExtract:
    """Measure async extract() with varying target counts."""

    @pytest.mark.parametrize("targets", [1, 3, 5, 10], ids=["1t", "3t", "5t", "10t"])
    def test_extract_targets(self, benchmark, targets):
        # Each target: 3 data pages + 1 empty sentinel = 4 responses
        single = [(_PAGE_25, 200)] * 3 + [(_EMPTY, 200)]
        pattern = single * targets

        def run():
            api = AsyncBlestaRequest("https://test.example.com/api", "u", "k")
            mock = _cycling_async_mock(pattern)
            target_list = [(f"model{i}", "getList") for i in range(targets)]
            with patch.object(api.client, "get", mock):
                return asyncio.run(api.extract(target_list))

        benchmark(run)


# ---------------------------------------------------------------------------
# Count helper
# ---------------------------------------------------------------------------


class TestAsyncCount:
    """Measure async count() overhead."""

    def test_count_overhead(self, benchmark):
        resp = _make_httpx_response(json.dumps({"response": 22376}), 200)

        def run():
            api = AsyncBlestaRequest("https://test.example.com/api", "u", "k")
            mock = AsyncMock(return_value=resp)
            with patch.object(api.client, "get", mock):
                return asyncio.run(api.count("transactions"))

        benchmark(run)


# ---------------------------------------------------------------------------
# Retry overhead
# ---------------------------------------------------------------------------


class TestAsyncRetry:
    """Measure async retry loop overhead (asyncio.sleep is mocked out)."""

    def test_retry_success_after_2(self, benchmark):
        pattern = [(_PAGE_EMPTY_500, 500), (_PAGE_EMPTY_500, 502), (_PAGE_25, 200)]

        def run():
            api = AsyncBlestaRequest(
                "https://test.example.com/api", "u", "k", max_retries=3
            )
            mock = _cycling_async_mock(pattern)
            with (
                patch.object(api.client, "get", mock),
                patch("blesta_sdk._async_client.asyncio.sleep", new_callable=AsyncMock),
            ):
                return asyncio.run(api.get("transactions", "getList"))

        benchmark(run)

    def test_retry_all_fail(self, benchmark):
        def run():
            api = AsyncBlestaRequest(
                "https://test.example.com/api", "u", "k", max_retries=3
            )
            mock = AsyncMock(return_value=_make_httpx_response(_PAGE_EMPTY_500, 500))
            with (
                patch.object(api.client, "get", mock),
                patch("blesta_sdk._async_client.asyncio.sleep", new_callable=AsyncMock),
            ):
                return asyncio.run(api.get("transactions", "getList"))

        benchmark(run)

    def test_no_retry_baseline(self, benchmark):
        """Baseline: max_retries=0, no retry overhead."""

        def run():
            api = AsyncBlestaRequest("https://test.example.com/api", "u", "k")
            mock = AsyncMock(return_value=_make_httpx_response(_PAGE_25, 200))
            with patch.object(api.client, "get", mock):
                return asyncio.run(api.get("transactions", "getList"))

        benchmark(run)


# ---------------------------------------------------------------------------
# Report series
# ---------------------------------------------------------------------------


class TestAsyncReportSeries:
    """Measure async get_report_series with mocked monthly reports."""

    @pytest.mark.parametrize("months", [3, 6, 12], ids=["3mo", "6mo", "12mo"])
    def test_report_series(self, benchmark, months):
        end_map = {3: "2025-03", 6: "2025-06", 12: "2025-12"}

        def run():
            api = AsyncBlestaRequest("https://test.example.com/api", "u", "k")
            mock = AsyncMock(return_value=_make_httpx_response(_CSV_REPORT, 200))
            with patch.object(api.client, "get", mock):
                return asyncio.run(
                    api.get_report_series("package_revenue", "2025-01", end_map[months])
                )

        benchmark(run)
