"""SDK exception types.

This module is not part of the public API. Import exception classes
from ``blesta_sdk`` directly.
"""

from __future__ import annotations

from collections.abc import Mapping
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


class BlestaError(Exception):
    """Base exception for Blesta SDK errors.

    :param message: Human-readable error description.
    :param status_code: HTTP status code (``0`` for connection errors).
    :param errors: Error details from the API response.
    :param headers: HTTP response headers.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 0,
        errors: dict[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.errors = errors
        self.headers: Mapping[str, str] = headers or {}


class BlestaConnectionError(BlestaError):
    """Raised when the HTTP request fails to connect."""


class BlestaAPIError(BlestaError):
    """Raised on 4xx client errors."""


class BlestaAuthError(BlestaAPIError):
    """Raised on 401/403 authentication or authorization errors."""


class BlestaRateLimitError(BlestaAPIError):
    """Raised on 429 Too Many Requests.

    :param retry_after: Parsed ``Retry-After`` value in seconds, or
        ``None`` if the header was absent or unparseable.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 429,
        errors: dict[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(
            message, status_code=status_code, errors=errors, headers=headers
        )
        self.retry_after = retry_after


class BlestaServerError(BlestaError):
    """Raised on 5xx server errors."""
