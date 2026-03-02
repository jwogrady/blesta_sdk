"""SDK exception types.

This module is not part of the public API. Import
:class:`~blesta_sdk.PaginationError` from ``blesta_sdk`` directly.
"""

from __future__ import annotations

from typing import Any


class PaginationError(Exception):
    """Raised when pagination encounters a non-200 response.

    Contains the partial results collected before the error, the page
    number that failed, and the HTTP status code.

    :param message: Human-readable error description.
    :param page: The page number that returned a non-200 status.
    :param status_code: The HTTP status code received.
    :param partial_items: Items collected before the error occurred.
    """

    def __init__(
        self,
        message: str,
        *,
        page: int,
        status_code: int,
        partial_items: list[Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.page = page
        self.status_code = status_code
        self.partial_items: list[Any] = (
            partial_items if partial_items is not None else []
        )
