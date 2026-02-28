from __future__ import annotations

import json
from typing import Any, Optional


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

    def errors(self) -> Optional[dict[str, Any]]:
        """
        Returns any errors present in the response.

        :return: Dictionary of errors, or None if no errors.
        """
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
