"""Internal async HTTP client implementation.

This module is not part of the public API. Import
:class:`~blesta_sdk.AsyncBlestaRequest` from ``blesta_sdk`` directly.

Requires ``httpx``: ``pip install blesta_sdk[async]``
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import random
from collections.abc import AsyncIterator
from typing import Any, Literal

import httpx

from blesta_sdk._dateutil import _month_boundaries
from blesta_sdk._exceptions import PaginationError
from blesta_sdk._response import BlestaResponse
from blesta_sdk._validation import validate_segment

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30

_IDEMPOTENT_METHODS = frozenset({"GET", "DELETE"})

_last_request_var: contextvars.ContextVar[dict[str, Any] | None] = (
    contextvars.ContextVar("_last_request_var", default=None)
)


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
        Only GET and DELETE are retried by default. Pass
        ``retry_mutations=True`` to also retry POST/PUT.
        Uses exponential backoff with jitter. Defaults to ``0`` (no retries).
    :param retry_mutations: Allow retrying non-idempotent methods
        (POST, PUT). Defaults to ``False``.
    :param max_connections: Maximum number of connections in the pool.
        Defaults to ``10``.
    :param max_keepalive_connections: Maximum number of idle keep-alive
        connections. Defaults to ``10``.
    :param max_concurrency: Maximum number of concurrent requests the
        client will issue (shared semaphore). Applies to
        :meth:`extract`, :meth:`get_all_fast`, and
        :meth:`get_report_series_concurrent`. Defaults to ``10``.
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
        retry_mutations: bool = False,
        max_connections: int = 10,
        max_keepalive_connections: int = 10,
        max_concurrency: int = 10,
        auth_method: Literal["basic", "header"] = "basic",
    ):
        self.base_url = url.rstrip("/") + "/"
        self.user = user
        self.key = key
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_mutations = retry_mutations
        self.auth_method = auth_method
        self._last_request: dict[str, Any] | None = None
        self._semaphore = asyncio.Semaphore(max_concurrency)
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

    @staticmethod
    def _validate_segment(segment: str, name: str) -> None:
        validate_segment(segment, name)

    @staticmethod
    def _get_discovery() -> Any:
        """Return the module-level cached BlestaDiscovery singleton."""
        from blesta_sdk._discovery import _get_discovery

        return _get_discovery()

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

        Retries are only attempted for idempotent methods (GET, DELETE)
        unless ``retry_mutations=True`` was passed to the constructor.

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

        self._validate_segment(model, "model")
        self._validate_segment(method, "method")
        url = f"{self.base_url}{model}/{method}.json"
        request_info = {"url": url, "args": args}
        self._last_request = request_info
        _last_request_var.set(request_info)

        can_retry = self.retry_mutations or action in _IDEMPOTENT_METHODS
        effective_retries = self.max_retries if can_retry else 0

        last_response: BlestaResponse | None = None
        for attempt in range(effective_retries + 1):
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

                if response.status_code < 500 or attempt == effective_retries:
                    return last_response

                logger.warning(
                    "Retry %d/%d: HTTP %d from %s",
                    attempt + 1,
                    effective_retries,
                    response.status_code,
                    url,
                )

            except httpx.HTTPError as e:
                logger.error("Request failed: %s", e)
                last_response = BlestaResponse(str(e), 0)

                if attempt == effective_retries:
                    return last_response

                logger.warning("Retry %d/%d: %s", attempt + 1, effective_retries, e)

            base_delay = 2**attempt
            await asyncio.sleep(
                base_delay * (0.5 + random.random() * 0.5)  # noqa: S311
            )

        if last_response is None:  # pragma: no cover
            raise RuntimeError("Retry loop exited without a response")
        return last_response

    async def iter_all(
        self,
        model: str,
        method: str,
        args: dict[str, Any] | None = None,
        start_page: int = 1,
        max_pages: int | None = None,
        on_error: Literal["raise", "warn"] = "warn",
    ) -> AsyncIterator[Any]:
        """Yield individual items across all pages.

        Calls the API with ``page=1``, ``page=2``, etc. until an empty
        response is returned.

        :param model: API model (e.g., ``"invoices"``).
        :param method: API method (e.g., ``"getList"``).
        :param args: Query parameters (``page`` is managed automatically).
        :param start_page: Page number to start from.
        :param max_pages: Maximum number of pages to fetch. ``None``
            means no limit.
        :param on_error: Behavior on non-200 status codes. ``"raise"``
            raises :class:`~blesta_sdk.PaginationError` with partial
            results attached. ``"warn"`` logs a warning and stops
            iteration (backward-compatible default).
        :return: Async iterator of individual result items.
        :raises PaginationError: If *on_error* is ``"raise"`` and a
            non-200 response is received.
        """
        base_args = args or {}

        page = start_page
        pages_fetched = 0
        collected: list[Any] = []
        prev_data: list[Any] | None = None
        repeat_count = 0

        while True:
            if max_pages is not None and pages_fetched >= max_pages:
                return

            response = await self.get(model, method, {**base_args, "page": page})

            if response.status_code != 200:
                if on_error == "raise":
                    raise PaginationError(
                        f"Pagination error: HTTP {response.status_code} on page {page}",
                        page=page,
                        status_code=response.status_code,
                        partial_items=collected,
                    )
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
                if prev_data is not None and data == prev_data:
                    repeat_count += 1
                    if repeat_count >= 3:
                        logger.error(
                            "Pagination aborted: page %d returned identical "
                            "data %d times consecutively",
                            page,
                            repeat_count + 1,
                        )
                        return
                else:
                    repeat_count = 0
                prev_data = data

                collected.extend(data)
                for item in data:
                    yield item
            else:
                collected.append(data)
                yield data
                return

            pages_fetched += 1
            page += 1

    async def get_all(
        self,
        model: str,
        method: str,
        args: dict[str, Any] | None = None,
        start_page: int = 1,
        max_pages: int | None = None,
    ) -> list[Any]:
        """Fetch all pages and return results as a single list.

        Convenience wrapper around :meth:`iter_all`.

        .. warning::
            Materializes all records into memory. For large datasets
            (100k+ records), prefer :meth:`iter_all` or
            :meth:`iter_pages` to process records in a streaming
            fashion.

        :param model: API model (e.g., ``"invoices"``).
        :param method: API method (e.g., ``"getList"``).
        :param args: Query parameters (``page`` is managed automatically).
        :param start_page: Page number to start from.
        :param max_pages: Maximum number of pages to fetch. ``None``
            means no limit.
        :return: List of all result items across all pages.
        """
        results: list[Any] = []
        async for item in self.iter_all(model, method, args, start_page, max_pages):
            results.append(item)
        return results

    async def iter_pages(
        self,
        model: str,
        method: str,
        args: dict[str, Any] | None = None,
        start_page: int = 1,
        max_pages: int | None = None,
        on_error: Literal["raise", "warn"] = "warn",
    ) -> AsyncIterator[list[Any]]:
        """Yield each page of results as a separate list.

        Unlike :meth:`iter_all` (which yields individual items),
        this method yields one list per API page — useful for
        batch-flushing to a database or file.

        :param model: API model (e.g., ``"invoices"``).
        :param method: API method (e.g., ``"getList"``).
        :param args: Query parameters (``page`` is managed automatically).
        :param start_page: Page number to start from.
        :param max_pages: Maximum number of pages to fetch.
        :param on_error: Behavior on non-200 status codes. ``"raise"``
            raises :class:`~blesta_sdk.PaginationError` with partial
            page count. ``"warn"`` logs a warning and stops
            iteration (backward-compatible default).
        :return: Async iterator of page lists.
        :raises PaginationError: If *on_error* is ``"raise"`` and a
            non-200 response is received.
        """
        base_args = args or {}
        page = start_page
        pages_fetched = 0
        prev_data: list[Any] | None = None
        repeat_count = 0

        while True:
            if max_pages is not None and pages_fetched >= max_pages:
                return

            response = await self.get(model, method, {**base_args, "page": page})
            if response.status_code != 200:
                if on_error == "raise":
                    raise PaginationError(
                        f"Pagination error: HTTP {response.status_code} on page {page}",
                        page=page,
                        status_code=response.status_code,
                    )
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
                if prev_data is not None and data == prev_data:
                    repeat_count += 1
                    if repeat_count >= 3:
                        logger.error(
                            "Pagination aborted: page %d returned identical "
                            "data %d times consecutively",
                            page,
                            repeat_count + 1,
                        )
                        return
                else:
                    repeat_count = 0
                prev_data = data

                yield data
            else:
                yield [data]
                return

            pages_fetched += 1
            page += 1

    async def get_all_fast(
        self,
        model: str,
        method: str,
        count_method: str = "getListCount",
        args: dict[str, Any] | None = None,
        page_size: int = 25,
        batch_size: int = 10,
        verify: bool = False,
    ) -> list[Any]:
        """Fetch all pages in parallel batches using a count-first strategy.

        Calls :meth:`count` to determine total records, then fetches
        pages concurrently in batches of *batch_size* via
        :func:`asyncio.gather`. Falls back to :meth:`get_all` if the
        count call returns ``0`` or fails.

        .. note::
            The count is a snapshot; records may change between the
            count and fetch phases (TOCTOU). Set ``verify=True`` to
            re-count after fetching and log a warning on mismatch.

        :param model: API model (e.g., ``"transactions"``).
        :param method: API method (e.g., ``"getList"``).
        :param count_method: Count method name. Defaults to
            ``"getListCount"``.
        :param args: Query parameters (``page`` is managed automatically).
        :param page_size: Expected items per page. Must match the API's
            page size. Defaults to ``25``.
        :param batch_size: Pages to fetch in parallel per batch.
            Defaults to ``10``.
        :param verify: If ``True``, re-count after fetching and log
            a warning if the count changed. Defaults to ``False``.
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
                async with self._semaphore:
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

        if verify:
            new_total = await self.count(model, count_method, args)
            if new_total != total:
                logger.warning(
                    "get_all_fast: count changed during fetch "
                    "(%d -> %d) for %s/%s; results may be inconsistent",
                    total,
                    new_total,
                    model,
                    method,
                )

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

        Uses :func:`asyncio.gather` to run all targets in parallel,
        limited by the client-level semaphore (``max_concurrency``).
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
                rows.append({**row, "_period": period})
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
            uses the client-level ``max_concurrency`` semaphore.
        :return: Flat list of row dicts from all months, ordered by period.
        :raises ValueError: If *start_month* is after *end_month* or
            the format is invalid.
        """
        boundaries = _month_boundaries(start_month, end_month)
        sem = asyncio.Semaphore(max_concurrency) if max_concurrency else self._semaphore

        async def _fetch_month(
            first_day: str, last_day: str, period: str
        ) -> tuple[str, BlestaResponse]:
            async with sem:
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
                rows.append({**row, "_period": period})
        return rows

    async def call(
        self,
        model: str,
        method: str,
        args: dict[str, Any] | None = None,
        action: str | None = None,
    ) -> BlestaResponse:
        """Call an API method, inferring the HTTP method from the schema.

        Uses :class:`~blesta_sdk.BlestaDiscovery` to resolve the correct
        HTTP method when *action* is ``None``. If the schema cannot
        resolve the method, falls back to a safe prefix-based heuristic
        (e.g. ``get*`` -> GET, ``create*`` -> POST). If still ambiguous,
        defaults to POST with a warning.

        :param model: API model (e.g., ``"clients"``).
        :param method: API method (e.g., ``"getList"``).
        :param args: Request parameters.
        :param action: Explicit HTTP method override. If ``None``,
            the method is inferred from the schema.
        :return: Parsed API response.
        """
        if action is None:
            from blesta_sdk._discovery import _infer_http_method

            _sentinel = "_UNRESOLVED_"
            disco = self._get_discovery()
            action = disco.resolve_http_method(model, method, default=_sentinel)
            if action == _sentinel:
                inferred = _infer_http_method(method)
                if inferred is not None:
                    action = inferred
                else:
                    action = "POST"
                    logger.warning(
                        "call(%s, %s): schema unavailable and method name "
                        "is ambiguous; falling back to POST. Specify "
                        "action explicitly to silence this warning.",
                        model,
                        method,
                    )
        return await self.submit(model, method, args, action)  # type: ignore[arg-type]

    async def call_all(
        self,
        model: str,
        method: str,
        args: dict[str, Any] | None = None,
        start_page: int = 1,
    ) -> list[Any]:
        """Paginate an API method, inferring the HTTP verb from the schema.

        Convenience wrapper around :meth:`get_all` that uses schema
        discovery to confirm the method should be called via GET.

        :param model: API model (e.g., ``"invoices"``).
        :param method: API method (e.g., ``"getList"``).
        :param args: Query parameters.
        :param start_page: Page number to start from.
        :return: List of all result items across all pages.
        """
        return await self.get_all(model, method, args, start_page)

    async def count_for(
        self,
        model: str,
        list_method: str = "getList",
        args: dict[str, Any] | None = None,
    ) -> int:
        """Fetch the record count for a paginated list method.

        Uses :class:`~blesta_sdk.BlestaDiscovery` to find the matching
        count method (e.g., ``"getList"`` -> ``"getListCount"``). Falls
        back to ``list_method + "Count"`` if the schema is unavailable.

        :param model: API model (e.g., ``"transactions"``).
        :param list_method: The list method to find a count for.
        :param args: Query parameters.
        :return: Record count, or ``0`` on errors.
        """
        disco = self._get_discovery()
        count_method = disco.suggest_pagination_pair(model, list_method)
        if count_method is None:
            count_method = list_method + "Count"
        return await self.count(model, count_method, args)

    def get_last_request(self) -> dict[str, Any] | None:
        """Return details of the last request made.

        In concurrent contexts, returns the last request from the
        current asyncio task (via :class:`contextvars.ContextVar`).
        Falls back to the instance attribute for non-concurrent use.

        :return: Dict with ``"url"`` and ``"args"`` keys, or ``None``
            if no requests have been made.
        """
        ctx_val = _last_request_var.get(None)
        if ctx_val is not None:
            return ctx_val
        return self._last_request
