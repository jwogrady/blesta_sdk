"""Concurrency benchmarks — latency-injected tests measuring real parallelism wins.

Uses simulated network latency (asyncio.sleep / time.sleep) to demonstrate
the throughput difference between sequential sync, sequential async, and
concurrent async patterns.

Run:
    uv run pytest benchmarks/test_bench_concurrency.py -v \
        --benchmark-sort=mean --benchmark-min-rounds=3
"""

import asyncio
import json
import time
from itertools import cycle
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from benchmarks.conftest import make_json_payload
from blesta_sdk import AsyncBlestaRequest, BlestaRequest

# ---------------------------------------------------------------------------
# Latency injection helpers
# ---------------------------------------------------------------------------

_CSV_REPORT = "Package,Revenue\nPkg1,100\nPkg2,200"
_PAGE_25 = make_json_payload(25)
_EMPTY = json.dumps({"response": []})


def _sync_delayed_response(text: str, status_code: int, delay: float) -> Mock:
    """Return a Mock whose call triggers time.sleep(delay) then returns a response."""
    resp = Mock(text=text, status_code=status_code)

    def side_effect(*args, **kwargs):
        time.sleep(delay)
        return resp

    return Mock(side_effect=side_effect)


def _sync_cycling_delayed(pattern: list[tuple[str, int]], delay: float) -> Mock:
    """Return a Mock that cycles through (text, status) with delay per call."""
    responses = cycle([Mock(text=t, status_code=s) for t, s in pattern])

    def side_effect(*args, **kwargs):
        time.sleep(delay)
        return next(responses)

    return Mock(side_effect=side_effect)


def _async_delayed_response(text: str, status_code: int, delay: float) -> AsyncMock:
    """Return an AsyncMock with asyncio.sleep(delay) before returning."""
    resp = httpx.Response(status_code, text=text)

    async def side_effect(*args, **kwargs):
        await asyncio.sleep(delay)
        return resp

    return AsyncMock(side_effect=side_effect)


def _async_cycling_delayed(pattern: list[tuple[str, int]], delay: float) -> AsyncMock:
    """Return an AsyncMock that cycles through (text, status) with delay."""
    responses = cycle([httpx.Response(s, text=t) for t, s in pattern])

    async def side_effect(*args, **kwargs):
        await asyncio.sleep(delay)
        return next(responses)

    return AsyncMock(side_effect=side_effect)


# ---------------------------------------------------------------------------
# Report series latency — 12 months
# ---------------------------------------------------------------------------


class TestReportSeriesLatency:
    """Compare sequential vs concurrent report fetching over 12 months.

    Expected: sync ~= 12*delay, async sequential ~= 12*delay,
    async concurrent ~= 1*delay.
    """

    @pytest.mark.parametrize("delay", [0.05, 0.1, 0.2], ids=["50ms", "100ms", "200ms"])
    def test_sync_sequential(self, benchmark, delay):
        """Baseline: sync get_report_series — 12 sequential requests."""
        api = BlestaRequest("https://test.example.com/api", "u", "k")
        mock = _sync_delayed_response(_CSV_REPORT, 200, delay)
        with patch.object(api.session, "get", mock):
            benchmark(api.get_report_series, "package_revenue", "2025-01", "2025-12")

    @pytest.mark.parametrize("delay", [0.05, 0.1, 0.2], ids=["50ms", "100ms", "200ms"])
    def test_async_sequential(self, benchmark, delay):
        """Async get_report_series — still sequential (12 serial awaits)."""
        loop = asyncio.new_event_loop()
        api = AsyncBlestaRequest("https://test.example.com/api", "u", "k")
        mock = _async_delayed_response(_CSV_REPORT, 200, delay)

        with patch.object(api.client, "get", mock):
            benchmark(
                lambda: loop.run_until_complete(
                    api.get_report_series("package_revenue", "2025-01", "2025-12")
                )
            )

        loop.run_until_complete(api.close())
        loop.close()

    @pytest.mark.parametrize("delay", [0.05, 0.1, 0.2], ids=["50ms", "100ms", "200ms"])
    def test_async_concurrent(self, benchmark, delay):
        """Async get_report_series_concurrent — all 12 months in parallel."""
        loop = asyncio.new_event_loop()
        api = AsyncBlestaRequest("https://test.example.com/api", "u", "k")
        mock = _async_delayed_response(_CSV_REPORT, 200, delay)

        with patch.object(api.client, "get", mock):
            benchmark(
                lambda: loop.run_until_complete(
                    api.get_report_series_concurrent(
                        "package_revenue", "2025-01", "2025-12"
                    )
                )
            )

        loop.run_until_complete(api.close())
        loop.close()


# ---------------------------------------------------------------------------
# Extract latency — 5 targets x 4 pages each
# ---------------------------------------------------------------------------


class TestExtractLatency:
    """Compare sync sequential extract vs async gather extract.

    5 targets, 4 pages each = 20 total requests.
    Expected: sync ~= 20*delay, async ~= 4*delay (gather across targets).
    """

    TARGETS = [
        ("clients", "getList"),
        ("invoices", "getList"),
        ("transactions", "getList"),
        ("services", "getList"),
        ("contacts", "getList"),
    ]

    @pytest.mark.parametrize("delay", [0.05, 0.1], ids=["50ms", "100ms"])
    def test_sync_5_targets(self, benchmark, delay):
        """Sync extract — 5 targets x (3 data pages + 1 empty) = 20 requests."""
        api = BlestaRequest("https://test.example.com/api", "u", "k")
        pattern = [(_PAGE_25, 200)] * 3 + [(_EMPTY, 200)]
        mock = _sync_cycling_delayed(pattern * 5, delay)
        with patch.object(api.session, "get", mock):
            benchmark(api.extract, self.TARGETS)

    @pytest.mark.parametrize("delay", [0.05, 0.1], ids=["50ms", "100ms"])
    def test_async_5_targets(self, benchmark, delay):
        """Async extract — 5 targets gathered, each paginating 4 requests."""
        loop = asyncio.new_event_loop()
        api = AsyncBlestaRequest("https://test.example.com/api", "u", "k")
        pattern = [(_PAGE_25, 200)] * 3 + [(_EMPTY, 200)]
        mock = _async_cycling_delayed(pattern * 5, delay)

        with patch.object(api.client, "get", mock):
            benchmark(lambda: loop.run_until_complete(api.extract(self.TARGETS)))

        loop.run_until_complete(api.close())
        loop.close()


# ---------------------------------------------------------------------------
# Pagination batch latency — 50 pages
# ---------------------------------------------------------------------------


class TestPaginationBatchLatency:
    """Compare sequential pagination vs count-first batched parallel.

    50 pages of 25 items = 1250 records.
    Sequential: 50 data + 1 empty = 51 requests.
    Count-first: 1 count + 50 data = 51 requests, but data fetched in batches.
    """

    @pytest.mark.parametrize("delay", [0.05, 0.1], ids=["50ms", "100ms"])
    def test_sync_sequential_50_pages(self, benchmark, delay):
        """Sync get_all — 51 sequential requests."""
        api = BlestaRequest("https://test.example.com/api", "u", "k")
        pattern = [(_PAGE_25, 200)] * 50 + [(_EMPTY, 200)]
        mock = _sync_cycling_delayed(pattern, delay)
        with patch.object(api.session, "get", mock):
            benchmark(api.get_all, "transactions", "getList")

    @pytest.mark.parametrize("delay", [0.05, 0.1], ids=["50ms", "100ms"])
    def test_async_sequential_50_pages(self, benchmark, delay):
        """Async get_all — 51 sequential awaits."""
        loop = asyncio.new_event_loop()
        api = AsyncBlestaRequest("https://test.example.com/api", "u", "k")
        pattern = [(_PAGE_25, 200)] * 50 + [(_EMPTY, 200)]
        mock = _async_cycling_delayed(pattern, delay)

        with patch.object(api.client, "get", mock):
            benchmark(
                lambda: loop.run_until_complete(api.get_all("transactions", "getList"))
            )

        loop.run_until_complete(api.close())
        loop.close()

    @pytest.mark.parametrize("delay", [0.05, 0.1], ids=["50ms", "100ms"])
    def test_async_count_first_50_pages(self, benchmark, delay):
        """Async get_all_fast — 1 count + 50 pages in batches of 10."""
        loop = asyncio.new_event_loop()
        api = AsyncBlestaRequest("https://test.example.com/api", "u", "k")

        count_resp = httpx.Response(200, text=json.dumps({"response": 1250}))
        data_resp = httpx.Response(200, text=_PAGE_25)

        async def delayed_get(url, *args, **kwargs):
            await asyncio.sleep(delay)
            if "getListCount" in str(url):
                return count_resp
            return data_resp

        with patch.object(api.client, "get", AsyncMock(side_effect=delayed_get)):
            benchmark(
                lambda: loop.run_until_complete(
                    api.get_all_fast(
                        "transactions",
                        "getList",
                        page_size=25,
                        batch_size=10,
                    )
                )
            )

        loop.run_until_complete(api.close())
        loop.close()
