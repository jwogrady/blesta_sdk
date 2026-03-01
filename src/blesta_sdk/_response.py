"""Internal response parsing implementation.

This module is not part of the public API. Import
:class:`~blesta_sdk.BlestaResponse` from ``blesta_sdk`` directly.
"""

from __future__ import annotations

import csv
import io
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas


_UNSET = object()


class BlestaResponse:
    """Parsed response from the Blesta API.

    Wraps the raw HTTP response text and status code. Provides
    properties for accessing parsed JSON data, CSV data, and errors.

    :param response: Raw response body text.
    :param status_code: HTTP status code.
    """

    def __init__(self, response: str | None, status_code: int):
        self._raw = response
        self._status_code = status_code
        self._parsed: dict[str, Any] | None = None
        self._json_valid: bool | None = None
        self._csv_cache: list[dict[str, str]] | None | object = _UNSET

    def __repr__(self) -> str:
        if self._raw and len(self._raw) > 80:
            body = self._raw[:80] + "..."
        else:
            body = self._raw
        return f"BlestaResponse(status_code={self._status_code}, body={body!r})"

    @property
    def data(self) -> Any | None:
        """Parsed ``"response"`` field from the JSON body.

        Returns ``None`` if the key is absent or the body is not JSON.
        """
        formatted = self._format_response()
        return formatted.get("response")

    @property
    def status_code(self) -> int:
        """HTTP status code of the response."""
        return self._status_code

    @property
    def raw(self) -> str | None:
        """Raw response body text."""
        return self._raw

    @property
    def is_json(self) -> bool:
        """Returns True if the raw response is valid JSON."""
        if self._json_valid is None:
            self._format_response()
        return bool(self._json_valid)

    @property
    def is_csv(self) -> bool:
        """Returns True if the raw response appears to be CSV data."""
        if self.is_json:
            return False
        if not self._raw or not self._raw.strip():
            return False
        lines = self._raw.strip().splitlines()
        if len(lines) < 2:
            return False
        return "," in lines[0]

    @property
    def csv_data(self) -> list[dict[str, str]] | None:
        """Parse the raw response as CSV.

        Results are cached after the first access to avoid re-parsing.

        :return: List of dicts (one per row, keyed by header column),
            or ``None`` if :attr:`is_csv` is ``False``.
        """
        if self._csv_cache is not _UNSET:
            return self._csv_cache  # type: ignore[return-value]
        if not self.is_csv:
            self._csv_cache = None
            return None
        reader = csv.DictReader(io.StringIO(self._raw))
        self._csv_cache = list(reader)
        return self._csv_cache

    def to_dataframe(self) -> pandas.DataFrame:
        """Convert the response to a :class:`pandas.DataFrame`.

        CSV responses are parsed via :attr:`csv_data`. JSON responses
        are normalized with :func:`pandas.json_normalize`.

        Requires ``pandas`` (``pip install pandas``).

        :return: DataFrame of the response data.
        :raises ImportError: If pandas is not installed.
        :raises ValueError: If the response contains no parseable data.
        """
        try:
            import pandas as pd
        except ImportError as err:
            raise ImportError(
                "pandas is required for to_dataframe(). "
                "Install it with: pip install pandas"
            ) from err

        if self.is_csv:
            data = self.csv_data
            if not data:
                return pd.DataFrame()
            return pd.DataFrame(data)

        if self.is_json:
            data = self.data
            if data is None:
                raise ValueError("JSON response has no 'response' key (data is None)")
            if isinstance(data, (list, dict)):
                return pd.json_normalize(data)
            raise ValueError(
                f"Cannot convert response of type {type(data).__name__} "
                f"to DataFrame"
            )

        raise ValueError(
            "Response is neither CSV nor JSON; cannot convert to DataFrame"
        )

    def errors(self) -> dict[str, Any] | None:
        """Extract error information from the response.

        :return: Dict of errors, or ``None`` on success.
        """
        if self.is_csv:
            if self._status_code != 200:
                return {"error": f"CSV response with HTTP {self._status_code}"}
            return None
        formatted = self._format_response()
        if self._status_code != 200:
            return formatted.get(
                "errors", {"error": f"HTTP {self._status_code} with no error details"}
            )
        if "error" in formatted:
            return {"error": formatted["error"]}
        return None

    def _format_response(self) -> dict[str, Any]:
        """Parse raw response as JSON, returning a fallback on failure."""
        if self._parsed is None:
            try:
                self._parsed = json.loads(self._raw)
                self._json_valid = True
            except (json.JSONDecodeError, TypeError):
                self._parsed = {"error": "Invalid JSON response"}
                self._json_valid = False
        return self._parsed
