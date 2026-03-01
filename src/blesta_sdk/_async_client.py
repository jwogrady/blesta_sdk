"""Internal async HTTP client implementation.

This module is not part of the public API. Import
:class:`~blesta_sdk.AsyncBlestaRequest` from ``blesta_sdk`` directly.

Requires ``httpx``: ``pip install blesta_sdk[async]``
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any, Literal
from urllib.parse import urljoin

import httpx

from blesta_sdk._dateutil import _month_boundaries
from blesta_sdk._response import BlestaResponse

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30


class AsyncBlestaRequest:
    """Async HTTP client for the Blesta REST API.

    Wraps :class:`httpx.AsyncClient` with Basic Auth and provides
    async convenience methods for GET/POST/PUT/DELETE, automatic
    pagination, and report fetching.

    Can be used as an async context manager::

        async with AsyncBlestaRequest(url, user, key) as api:
            response = await api.get("clients", "getList")

    :param url: Base URL of the Blesta API (e.g., ``"https://example.com/api"``).
    :param user: API username.
    :param key: API key.
    :param timeout: Request timeout in seconds. Applied at client
        initialization and cannot be changed afterward (unlike the sync
        client, where timeout is passed per-request).
    :param max_retries: Number of retries on network errors or 5xx responses.
        Uses exponential backoff (1s, 2s, 4s, …). Defaults to ``0`` (no retries).
    :param max_connections: Maximum number of connections in the pool.
        Defaults to ``10``.
    :param max_keepalive_connections: Maximum number of idle keep-alive
        connections. Defaults to ``10``.
    :param auth_method: Authentication method. ``"basic"`` uses HTTP Basic
        Auth. ``"header"`` sends credentials via ``BLESTA-API-USER`` and
        ``BLESTA-API-KEY`` headers (recommended by Blesta, requires no
        server-side CGI/PHP-FPM configuration). Defaults to ``"basic"``.
    """

    def __init__(
        self,
        url: str,
        user: str,
        key: str,
        timeout: int | float = DEFAULT_TIMEOUT,
        max_retries: int = 0,
        max_connections: int = 10,
        max_keepalive_connections: int = 10,
        auth_method: Literal["basic", "header"] = "basic",
    ):
        self.base_url = url.rstrip("/") + "/"
        self.user = user
        self.key = key
        self.timeout = timeout
        self.max_retries = max_retries
        self.auth_method = auth_method
        self._last_request: dict[str, Any] | None = None
        auth = None if auth_method == "header" else httpx.BasicAuth(self.user, self.key)
        headers = {}
        if auth_method == "header":
            headers = {
                "BLESTA-API-USER": self.user,
                "BLESTA-API-KEY": self.key,
            }
        self.client = httpx.AsyncClient(
            auth=auth,
            headers=headers,
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_keepalive_connections,
            ),
        )

    async def __aenter__(self) -> AsyncBlestaRequest:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.client.aclose()

    def __repr__(self) -> str:
        return f"AsyncBlestaRequest(url={self.base_url!r}, user={self.user!r})"

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()

    async def get(
        self, model: str, method: str, args: dict[str, Any] | None = None
    ) -> BlestaResponse:
        """Send an async GET request. Parameters are passed as query strings.

        :param model: API model (e.g., ``"clients"``).
        :param method: API method (e.g., ``"getList"``).
        :param args: Query parameters.
        :return: Parsed API response.
        """
        return await self.submit(model, method, args, "GET")

    async def post(
        self, model: str, method: str, args: dict[str, Any] | None = None
    ) -> BlestaResponse:
        """Send an async POST request. Parameters are sent as a JSON body.

        :param model: API model (e.g., ``"clients"``).
        :param method: API method (e.g., ``"create"``).
        :param args: JSON body data.
        :return: Parsed API response.
        """
        return await self.submit(model, method, args, "POST")

    async def put(
        self, model: str, method: str, args: dict[str, Any] | None = None
    ) -> BlestaResponse:
        """Send an async PUT request. Parameters are sent as a JSON body.

        :param model: API model (e.g., ``"clients"``).
        :param method: API method (e.g., ``"edit"``).
        :param args: JSON body data.
        :return: Parsed API response.
        """
        return await self.submit(model, method, args, "PUT")

    async def delete(
        self, model: str, method: str, args: dict[str, Any] | None = None
    ) -> BlestaResponse:
        """Send an async DELETE request. Parameters are sent as a JSON body.

        :param model: API model (e.g., ``"clients"``).
        :param method: API method (e.g., ``"delete"``).
        :param args: JSON body data.
        :return: Parsed API response.
        """
        return await self.submit(model, method, args, "DELETE")

    async def submit(
        self,
        model: str,
        method: str,
        args: dict[str, Any] | None = None,
        action: Literal["GET", "POST", "PUT", "DELETE"] = "POST",
    ) -> BlestaResponse:
        """Send an async HTTP request to the Blesta API.

        Prefer :meth:`get`, :meth:`post`, :meth:`put`, or :meth:`delete`
        over calling this method directly.

        On network errors, returns a ``BlestaResponse`` with
        ``status_code=0`` and the exception message as raw text.

        :param model: API model (e.g., ``"clients"``). For plugin models
            use dot notation: ``"plugin.model"`` (builds
            ``plugin.model/method.json``).
        :param method: API method (e.g., ``"getList"``).
        :param args: Query parameters (GET) or JSON body (POST/PUT/DELETE).
        :param action: HTTP method — ``"GET"``, ``"POST"``, ``"PUT"``, or ``"DELETE"``.
        :return: Parsed API response.
        :raises ValueError: If *action* is not a recognized HTTP method.
        """
        if args is None:
            args = {}

        url = urljoin(self.base_url, f"{model}/{method}.json")
        self._last_request = {"url": url, "args": args}

        last_response: BlestaResponse | None = None
        for attempt in range(self.max_retries + 1):
            try:
                if action == "GET":
                    response = await self.client.get(url, params=args)
                elif action == "POST":
                    response = await self.client.post(url, json=args)
                elif action == "PUT":
                    response = await self.client.put(url, json=args)
                elif action == "DELETE":
                    response = await self.client.delete(url, json=args)
                else:
                    raise ValueError("Invalid HTTP action specified.")

                last_response = BlestaResponse(response.text, response.status_code)

                if response.status_code < 500 or attempt == self.max_retries:
                    return last_response

                logger.warning(
                    "Retry %d/%d: HTTP %d from %s",
                    attempt + 1,
                    self.max_retries,
                    response.status_code,
                    url,
                )

            except httpx.HTTPError as e:
                logger.error("Request failed: %s", e)
                last_response = BlestaResponse(str(e), 0)

                if attempt == self.max_retries:
                    return last_response

                logger.warning("Retry %d/%d: %s", attempt + 1, self.max_retries, e)

            await asyncio.sleep(2**attempt)

        if last_response is None:  # pragma: no cover
            raise RuntimeError("Retry loop exited without a response")
        return last_response

    async def iter_all(
        self,
        model: str,
        method: str,
        args: dict[str, Any] | None = None,
        start_page: int = 1,
    ) -> AsyncIterator[Any]:
        """Yield individual items across all pages.

        Calls the API with ``page=1``, ``page=2``, etc. until an empty
        response is returned. Stops on non-200 status codes.

        :param model: API model (e.g., ``"invoices"``).
        :param method: API method (e.g., ``"getList"``).
        :param args: Query parameters (``page`` is managed automatically).
        :param start_page: Page number to start from.
        :return: Async iterator of individual result items.
        """
        if args is None:
            args = {}

        page = start_page
        while True:
            page_args = {**args, "page": page}
            response = await self.get(model, method, page_args)

            if response.status_code != 200:
                logger.warning(
                    "Pagination stopped: HTTP %d on page %d",
                    response.status_code,
                    page,
                )
                return

            data = response.data
            if not data:
                return

            if isinstance(data, list):
                for item in data:
                    yield item
            else:
                yield data
                return

            page += 1

    async def get_all(
        self,
        model: str,
        method: str,
        args: dict[str, Any] | None = None,
        start_page: int = 1,
    ) -> list[Any]:
        """Fetch all pages and return results as a single list.

        Convenience wrapper around :meth:`iter_all`.

        :param model: API model (e.g., ``"invoices"``).
        :param method: API method (e.g., ``"getList"``).
        :param args: Query parameters (``page`` is managed automatically).
        :param start_page: Page number to start from.
        :return: List of all result items across all pages.
        """
        results: list[Any] = []
        async for item in self.iter_all(model, method, args, start_page):
            results.append(item)
        return results

    async def get_all_fast(
        self,
        model: str,
        method: str,
        count_method: str = "getListCount",
        args: dict[str, Any] | None = None,
        page_size: int = 25,
        batch_size: int = 10,
    ) -> list[Any]:
        """Fetch all pages in parallel batches using a count-first strategy.

        Calls :meth:`count` to determine total records, then fetches
        pages concurrently in batches of *batch_size* via
        :func:`asyncio.gather`. Falls back to :meth:`get_all` if the
        count call returns ``0`` or fails.

        :param model: API model (e.g., ``"transactions"``).
        :param method: API method (e.g., ``"getList"``).
        :param count_method: Count method name. Defaults to
            ``"getListCount"``.
        :param args: Query parameters (``page`` is managed automatically).
        :param page_size: Expected items per page. Must match the API's
            page size. Defaults to ``25``.
        :param batch_size: Pages to fetch in parallel per batch.
            Defaults to ``10``.
        :return: List of all result items across all pages.
        """
        if args is None:
            args = {}

        total = await self.count(model, count_method, args)
        if total <= 0:
            logger.debug(
                "get_all_fast: count returned %d for %s/%s, " "falling back to get_all",
                total,
                model,
                method,
            )
            return await self.get_all(model, method, args)

        total_pages = -(-total // page_size)  # ceil division
        logger.debug(
            "get_all_fast: %d records, %d pages for %s/%s",
            total,
            total_pages,
            model,
            method,
        )

        all_items: list[Any] = []

        for batch_start in range(1, total_pages + 1, batch_size):
            batch_end = min(batch_start + batch_size, total_pages + 1)

            async def _fetch_page(page: int) -> list[Any]:
                page_args = {**args, "page": page}
                response = await self.get(model, method, page_args)
                if response.status_code != 200:
                    logger.warning(
                        "get_all_fast: HTTP %d on page %d",
                        response.status_code,
                        page,
                    )
                    return []
                data = response.data
                if not data:
                    return []
                return data if isinstance(data, list) else [data]

            pages_data = await asyncio.gather(
                *[_fetch_page(p) for p in range(batch_start, batch_end)]
            )
            for page_items in pages_data:
                all_items.extend(page_items)

        return all_items

    async def count(
        self,
        model: str,
        method: str = "getListCount",
        args: dict[str, Any] | None = None,
    ) -> int:
        """Fetch a record count from a Blesta ``*Count`` method.

        Many Blesta models expose a ``getListCount`` method that returns
        a single integer.  This method wraps that call and returns the
        count as a Python :class:`int`.

        :param model: API model (e.g., ``"transactions"``).
        :param method: Count method name.  Defaults to ``"getListCount"``.
        :param args: Query parameters.
        :return: Record count, or ``0`` on errors.
        """
        response = await self.get(model, method, args)
        if response.status_code != 200:
            logger.warning(
                "count() got HTTP %d for %s/%s", response.status_code, model, method
            )
            return 0
        data = response.data
        if data is None:
            return 0
        try:
            return int(data)
        except (TypeError, ValueError):
            logger.warning(
                "count() expected int-like response from %s/%s, got %s: %r",
                model,
                method,
                type(data).__name__,
                data,
            )
            return 0

    async def extract(
        self,
        targets: list[tuple[str, str] | tuple[str, str, dict[str, Any]]],
    ) -> dict[str, list[Any]]:
        """Fetch multiple paginated endpoints concurrently.

        Uses :func:`asyncio.gather` to run all targets in parallel.
        Each target is a tuple of ``(model, method)`` or
        ``(model, method, args)``.

        :param targets: List of extraction targets.
        :return: Dict mapping ``"model.method"`` to list of results.
        """

        async def _fetch(
            target: tuple[str, str] | tuple[str, str, dict[str, Any]],
        ) -> tuple[str, list[Any]]:
            if len(target) == 3:
                model, method, args = target  # type: ignore[misc]
            else:
                model, method = target  # type: ignore[misc]
                args = None
            key = f"{model}.{method}"
            data = await self.get_all(model, method, args)
            return key, data

        pairs = await asyncio.gather(*[_fetch(t) for t in targets])
        return dict(pairs)

    async def get_report(
        self,
        report_type: str,
        start_date: str,
        end_date: str,
        extra_vars: dict[str, str] | None = None,
    ) -> BlestaResponse:
        """Fetch a Blesta report via ``report_manager/fetchAll``.

        Automatically formats the ``vars[]`` parameters that Blesta
        expects. Report responses are typically CSV — use
        :attr:`~BlestaResponse.csv_data` to parse them.

        :param report_type: Report type (e.g., ``"package_revenue"``).
        :param start_date: Start date as ``"YYYY-MM-DD"``.
        :param end_date: End date as ``"YYYY-MM-DD"``.
        :param extra_vars: Additional ``vars[]`` parameters. Keys are
            auto-wrapped in ``vars[...]`` unless already wrapped.
        :return: Parsed API response (usually CSV).
        """
        args: dict[str, str] = {
            "type": report_type,
            "vars[start_date]": start_date,
            "vars[end_date]": end_date,
        }
        if extra_vars:
            for key, value in extra_vars.items():
                param_key = key if key.startswith("vars[") else f"vars[{key}]"
                args[param_key] = value

        return await self.get("report_manager", "fetchAll", args)

    async def get_report_series_pages(
        self,
        report_type: str,
        start_month: str,
        end_month: str,
        extra_vars: dict[str, str] | None = None,
    ) -> AsyncIterator[tuple[str, BlestaResponse]]:
        """Yield ``(period, response)`` for each month in a date range.

        Fetches one report per month via :meth:`get_report`. Yields
        all months including those that return errors, so the caller
        can decide how to handle failures.

        :param report_type: Report type (e.g., ``"package_revenue"``).
        :param start_month: Start month as ``"YYYY-MM"`` (inclusive).
        :param end_month: End month as ``"YYYY-MM"`` (inclusive).
        :param extra_vars: Additional ``vars[]`` parameters.
        :return: Async iterator of ``(period, BlestaResponse)`` tuples.
        :raises ValueError: If *start_month* is after *end_month* or
            the format is invalid.
        """
        boundaries = _month_boundaries(start_month, end_month)
        for first_day, last_day, period in boundaries:
            logger.debug("Fetching report %r for %s", report_type, period)
            response = await self.get_report(
                report_type, first_day, last_day, extra_vars
            )
            yield (period, response)

    async def get_report_series(
        self,
        report_type: str,
        start_month: str,
        end_month: str,
        extra_vars: dict[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """Fetch monthly reports and return all rows as a flat list.

        Convenience wrapper around :meth:`get_report_series_pages`.
        Each returned row dict has a ``"_period"`` key added with the
        ``"YYYY-MM"`` value. Months that return errors or non-CSV
        responses are skipped with a warning log.

        :param report_type: Report type (e.g., ``"package_revenue"``).
        :param start_month: Start month as ``"YYYY-MM"`` (inclusive).
        :param end_month: End month as ``"YYYY-MM"`` (inclusive).
        :param extra_vars: Additional ``vars[]`` parameters.
        :return: Flat list of row dicts from all months.
        :raises ValueError: If *start_month* is after *end_month* or
            the format is invalid.
        """
        rows: list[dict[str, str]] = []
        async for period, response in self.get_report_series_pages(
            report_type, start_month, end_month, extra_vars
        ):
            if response.status_code != 200:
                logger.warning(
                    "Report %r for %s: HTTP %d, skipping",
                    report_type,
                    period,
                    response.status_code,
                )
                continue
            csv_rows = response.csv_data
            if csv_rows is None:
                logger.warning(
                    "Report %r for %s: no CSV data in response, skipping",
                    report_type,
                    period,
                )
                continue
            for row in csv_rows:
                row["_period"] = period
            rows.extend(csv_rows)
        return rows

    async def get_report_series_concurrent(
        self,
        report_type: str,
        start_month: str,
        end_month: str,
        extra_vars: dict[str, str] | None = None,
        max_concurrency: int | None = None,
    ) -> list[dict[str, str]]:
        """Fetch monthly reports concurrently and return all rows.

        Unlike :meth:`get_report_series`, which fetches months
        sequentially, this method uses :func:`asyncio.gather` to fetch
        all months in parallel (or up to *max_concurrency* at a time
        via a semaphore).

        Each returned row dict has a ``"_period"`` key added with the
        ``"YYYY-MM"`` value. Months that return errors or non-CSV
        responses are skipped with a warning log.

        :param report_type: Report type (e.g., ``"package_revenue"``).
        :param start_month: Start month as ``"YYYY-MM"`` (inclusive).
        :param end_month: End month as ``"YYYY-MM"`` (inclusive).
        :param extra_vars: Additional ``vars[]`` parameters.
        :param max_concurrency: Maximum concurrent requests. ``None``
            means unlimited (all months in parallel).
        :return: Flat list of row dicts from all months, ordered by period.
        :raises ValueError: If *start_month* is after *end_month* or
            the format is invalid.
        """
        boundaries = _month_boundaries(start_month, end_month)
        sem = asyncio.Semaphore(max_concurrency) if max_concurrency else None

        async def _fetch_month(
            first_day: str, last_day: str, period: str
        ) -> tuple[str, BlestaResponse]:
            if sem:
                async with sem:
                    resp = await self.get_report(
                        report_type, first_day, last_day, extra_vars
                    )
            else:
                resp = await self.get_report(
                    report_type, first_day, last_day, extra_vars
                )
            return (period, resp)

        results = await asyncio.gather(
            *[_fetch_month(fd, ld, p) for fd, ld, p in boundaries]
        )

        rows: list[dict[str, str]] = []
        for period, response in results:
            if response.status_code != 200:
                logger.warning(
                    "Report %r for %s: HTTP %d, skipping",
                    report_type,
                    period,
                    response.status_code,
                )
                continue
            csv_rows = response.csv_data
            if csv_rows is None:
                logger.warning(
                    "Report %r for %s: no CSV data in response, skipping",
                    report_type,
                    period,
                )
                continue
            for row in csv_rows:
                row["_period"] = period
            rows.extend(csv_rows)
        return rows

    def get_last_request(self) -> dict[str, Any] | None:
        """Return details of the last request made.

        :return: Dict with ``"url"`` and ``"args"`` keys, or ``None``
            if no requests have been made.
        """
        return self._last_request
