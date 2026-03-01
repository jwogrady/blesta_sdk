"""Internal HTTP client implementation.

This module is not part of the public API. Import
:class:`~blesta_sdk.BlestaRequest` from ``blesta_sdk`` directly.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any, Literal
from urllib.parse import urljoin

import requests
from requests.auth import HTTPBasicAuth

from blesta_sdk._dateutil import _month_boundaries
from blesta_sdk._response import BlestaResponse

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30


class BlestaRequest:
    """HTTP client for the Blesta REST API.

    Wraps :class:`requests.Session` with Basic Auth and provides
    convenience methods for GET/POST/PUT/DELETE, automatic pagination,
    and report fetching.

    Can be used as a context manager::

        with BlestaRequest(url, user, key) as api:
            response = api.get("clients", "getList")

    :param url: Base URL of the Blesta API (e.g., ``"https://example.com/api"``).
    :param user: API username.
    :param key: API key.
    :param timeout: Request timeout in seconds.
    """

    def __init__(self, url: str, user: str, key: str, timeout: int = DEFAULT_TIMEOUT):
        self.base_url = url.rstrip("/") + "/"
        self.user = user
        self.key = key
        self.timeout = timeout
        self._last_request: dict[str, Any] | None = None
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(self.user, self.key)

    def __enter__(self) -> BlestaRequest:
        return self

    def __exit__(self, *args: Any) -> None:
        self.session.close()

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self.session.close()

    def get(
        self, model: str, method: str, args: dict[str, Any] | None = None
    ) -> BlestaResponse:
        """Send a GET request. Parameters are passed as query strings.

        :param model: API model (e.g., ``"clients"``).
        :param method: API method (e.g., ``"getList"``).
        :param args: Query parameters.
        :return: Parsed API response.
        """
        return self.submit(model, method, args, "GET")

    def post(
        self, model: str, method: str, args: dict[str, Any] | None = None
    ) -> BlestaResponse:
        """Send a POST request. Parameters are sent as a JSON body.

        :param model: API model (e.g., ``"clients"``).
        :param method: API method (e.g., ``"create"``).
        :param args: JSON body data.
        :return: Parsed API response.
        """
        return self.submit(model, method, args, "POST")

    def put(
        self, model: str, method: str, args: dict[str, Any] | None = None
    ) -> BlestaResponse:
        """Send a PUT request. Parameters are sent as a JSON body.

        :param model: API model (e.g., ``"clients"``).
        :param method: API method (e.g., ``"edit"``).
        :param args: JSON body data.
        :return: Parsed API response.
        """
        return self.submit(model, method, args, "PUT")

    def delete(
        self, model: str, method: str, args: dict[str, Any] | None = None
    ) -> BlestaResponse:
        """Send a DELETE request. Parameters are sent as a JSON body.

        :param model: API model (e.g., ``"clients"``).
        :param method: API method (e.g., ``"delete"``).
        :param args: JSON body data.
        :return: Parsed API response.
        """
        return self.submit(model, method, args, "DELETE")

    def submit(
        self,
        model: str,
        method: str,
        args: dict[str, Any] | None = None,
        action: Literal["GET", "POST", "PUT", "DELETE"] = "POST",
    ) -> BlestaResponse:
        """Send an HTTP request to the Blesta API.

        Prefer :meth:`get`, :meth:`post`, :meth:`put`, or :meth:`delete`
        over calling this method directly.

        On network errors, returns a ``BlestaResponse`` with
        ``status_code=0`` and the exception message as raw text.

        :param model: API model (e.g., ``"clients"``).
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

        try:
            if action == "GET":
                response = self.session.get(url, params=args, timeout=self.timeout)
            elif action == "POST":
                response = self.session.post(url, json=args, timeout=self.timeout)
            elif action == "PUT":
                response = self.session.put(url, json=args, timeout=self.timeout)
            elif action == "DELETE":
                response = self.session.delete(url, json=args, timeout=self.timeout)
            else:
                raise ValueError("Invalid HTTP action specified.")

            return BlestaResponse(response.text, response.status_code)

        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            return BlestaResponse(str(e), 0)

    def iter_all(
        self,
        model: str,
        method: str,
        args: dict[str, Any] | None = None,
        start_page: int = 1,
    ) -> Iterator[Any]:
        """Yield individual items across all pages.

        Calls the API with ``page=1``, ``page=2``, etc. until an empty
        response is returned. Stops on non-200 status codes.

        :param model: API model (e.g., ``"invoices"``).
        :param method: API method (e.g., ``"getList"``).
        :param args: Query parameters (``page`` is managed automatically).
        :param start_page: Page number to start from.
        :return: Iterator of individual result items.
        """
        if args is None:
            args = {}

        page = start_page
        while True:
            page_args = {**args, "page": page}
            response = self.get(model, method, page_args)

            if response.status_code != 200:
                logger.warning(
                    f"Pagination stopped: HTTP {response.status_code} on page {page}"
                )
                return

            data = response.data
            if not data:
                return

            if isinstance(data, list):
                if len(data) == 0:
                    return
                yield from data
            else:
                yield data
                return

            page += 1

    def get_all(
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
        return list(self.iter_all(model, method, args, start_page))

    def get_report(
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

        return self.get("report_manager", "fetchAll", args)

    def get_report_series_pages(
        self,
        report_type: str,
        start_month: str,
        end_month: str,
        extra_vars: dict[str, str] | None = None,
    ) -> Iterator[tuple[str, BlestaResponse]]:
        """Yield ``(period, response)`` for each month in a date range.

        Fetches one report per month via :meth:`get_report`. Yields
        all months including those that return errors, so the caller
        can decide how to handle failures.

        :param report_type: Report type (e.g., ``"package_revenue"``).
        :param start_month: Start month as ``"YYYY-MM"`` (inclusive).
        :param end_month: End month as ``"YYYY-MM"`` (inclusive).
        :param extra_vars: Additional ``vars[]`` parameters.
        :return: Iterator of ``(period, BlestaResponse)`` tuples.
        :raises ValueError: If *start_month* is after *end_month* or
            the format is invalid.
        """
        boundaries = _month_boundaries(start_month, end_month)
        for first_day, last_day, period in boundaries:
            logger.debug(f"Fetching report {report_type!r} for {period}")
            response = self.get_report(report_type, first_day, last_day, extra_vars)
            yield (period, response)

    def get_report_series(
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
        for period, response in self.get_report_series_pages(
            report_type, start_month, end_month, extra_vars
        ):
            if response.status_code != 200:
                logger.warning(
                    f"Report {report_type!r} for {period}: "
                    f"HTTP {response.status_code}, skipping"
                )
                continue
            csv_rows = response.csv_data
            if csv_rows is None:
                logger.warning(
                    f"Report {report_type!r} for {period}: "
                    f"no CSV data in response, skipping"
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
