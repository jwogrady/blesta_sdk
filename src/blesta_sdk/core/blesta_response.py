from __future__ import annotations

import csv
import io
import json
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    import pandas


class BlestaResponse:
    """
    Blesta API response handler.
    """

    def __init__(self, response: str, status_code: int):
        """
        Initializes the BlestaResponse instance.

        :param response: The raw response data from an API request.
        :param status_code: The HTTP status code for the request.
        """
        self._raw = response
        self._status_code = status_code

    @property
    def response(self) -> Optional[Any]:
        """
        Returns the parsed 'response' data from the API request.

        :return: The value of the 'response' key if present, else None.
        """
        formatted = self._format_response()
        return formatted.get("response")

    @property
    def status_code(self) -> int:
        """
        Returns the HTTP status code.

        :return: The HTTP status code for the request.
        """
        return self._status_code

    @property
    def response_code(self) -> int:
        """
        Alias for :attr:`status_code` (deprecated, use ``status_code``).

        :return: The HTTP status code for the request.
        """
        return self._status_code

    @property
    def raw(self) -> str:
        """
        Returns the raw API response.

        :return: The raw response as a string.
        """
        return self._raw

    @property
    def is_json(self) -> bool:
        """Returns True if the raw response is valid JSON."""
        try:
            json.loads(self._raw)
            return True
        except (json.JSONDecodeError, TypeError):
            return False

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
    def csv_data(self) -> Optional[list[dict[str, str]]]:
        """
        Parses the raw response as CSV and returns a list of dicts.

        :return: List of dicts (one per row, keyed by header), or None if not CSV.
        """
        if not self.is_csv:
            return None
        reader = csv.DictReader(io.StringIO(self._raw))
        return list(reader)

    def to_dataframe(self) -> "pandas.DataFrame":
        """
        Converts the response data to a pandas DataFrame.

        For CSV responses, parses csv_data into a DataFrame.
        For JSON responses, uses pd.json_normalize on the response data.

        Requires pandas to be installed. Install with:
            pip install pandas

        :return: pandas DataFrame of the response data.
        :raises ImportError: If pandas is not installed.
        :raises ValueError: If the response contains no parseable data.
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "pandas is required for to_dataframe(). "
                "Install it with: pip install pandas"
            )

        if self.is_csv:
            data = self.csv_data
            if not data:
                return pd.DataFrame()
            return pd.DataFrame(data)

        if self.is_json:
            data = self.response
            if data is None:
                raise ValueError("JSON response has no 'response' key")
            if isinstance(data, (list, dict)):
                return pd.json_normalize(data)
            raise ValueError(
                f"Cannot convert response of type {type(data).__name__} "
                f"to DataFrame"
            )

        raise ValueError(
            "Response is neither CSV nor JSON; cannot convert to DataFrame"
        )

    def errors(self) -> Optional[dict[str, Any]]:
        """
        Returns any errors present in the response.

        :return: Dictionary of errors, or None if no errors.
        """
        if self.is_csv:
            if self._status_code != 200:
                return {"error": f"CSV response with HTTP {self._status_code}"}
            return None
        formatted = self._format_response()
        if self._status_code != 200:
            return formatted.get("errors", {"error": "Invalid JSON response"})
        if "error" in formatted:
            return {"error": formatted["error"]}
        return None

    def _format_response(self) -> dict[str, Any]:
        """
        Parses the raw response into a dictionary.

        :return: Parsed JSON response.
        """
        try:
            return json.loads(self._raw)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON response"}
