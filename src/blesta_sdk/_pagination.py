"""Shared pagination control-flow for sync and async clients.

This module is not part of the public API. Both :class:`BlestaRequest`
and :class:`AsyncBlestaRequest` delegate page-level decisions here to
avoid duplicating stop conditions, stuck-page detection, error handling,
and partial-item collection.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from blesta_sdk._exceptions import PaginationError
from blesta_sdk._response import BlestaResponse

logger = logging.getLogger(__name__)

_REPEAT_THRESHOLD = 3


class PaginationState:
    """Mutable state tracker for a single pagination run.

    Callers (sync/async) perform I/O and yielding; this class handles
    everything else: max-page gating, error checking, stuck-page
    detection, and partial-item collection for ``on_error='raise'``.

    :param start_page: First page number.
    :param max_pages: Page limit (``None`` = unlimited).
    :param on_error: ``"raise"`` or ``"warn"``.
    """

    def __init__(
        self,
        start_page: int,
        max_pages: int | None,
        on_error: Literal["raise", "warn"],
    ) -> None:
        self.page = start_page
        self.pages_fetched = 0
        self.collected: list[Any] | None = [] if on_error == "raise" else None
        self._max_pages = max_pages
        self._on_error = on_error
        self._prev_data: list[Any] | None = None
        self._repeat_count = 0

    def has_next_page(self) -> bool:
        """Return ``True`` if the loop should fetch another page."""
        return self._max_pages is None or self.pages_fetched < self._max_pages

    def check_response(self, response: BlestaResponse) -> bool:
        """Handle a non-200 response.

        :return: ``True`` if iteration should stop.
        :raises PaginationError: If ``on_error='raise'``.
        """
        if response.status_code == 200:
            return False
        if self._on_error == "raise":
            raise PaginationError(
                f"Pagination error: HTTP {response.status_code} on page {self.page}",
                page=self.page,
                status_code=response.status_code,
                partial_items=self.collected,
            )
        logger.warning(
            "Pagination stopped: HTTP %d on page %d",
            response.status_code,
            self.page,
        )
        return True

    def check_data(self, data: Any) -> bool:
        """Validate page data and detect stuck pagination.

        Must be called *before* yielding items.

        :return: ``True`` if iteration should stop.
        """
        if not data:
            return True

        if not isinstance(data, list):
            return False

        if self._prev_data is not None and data == self._prev_data:
            self._repeat_count += 1
            if self._repeat_count >= _REPEAT_THRESHOLD:
                logger.error(
                    "Pagination aborted: page %d returned identical "
                    "data %d times consecutively",
                    self.page,
                    self._repeat_count + 1,
                )
                return True
        else:
            self._repeat_count = 0
        self._prev_data = data
        return False

    def collect(self, data: Any) -> None:
        """Track items for :attr:`PaginationError.partial_items`."""
        if self.collected is None:
            return
        if isinstance(data, list):
            self.collected.extend(data)
        else:
            self.collected.append(data)

    def advance(self) -> None:
        """Increment page counter after a successful page yield."""
        self.pages_fetched += 1
        self.page += 1
