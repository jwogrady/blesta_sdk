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
# Rolling window size for alternating-page detection.
# Keeps a short history of recent page hashes to catch A→B→A→B loops
# that would otherwise reset _repeat_count on every page.
_WINDOW_SIZE = 6


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
        self._prev_data: Any = None
        self._prev_data_set: bool = False
        self._repeat_count = 0
        # Rolling window of recent page-data hashes for alternating-loop detection.
        self._page_hash_window: list[int] = []

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

    def _raise_or_stop(self, message: str) -> bool:
        """Raise ``PaginationError`` or return ``True`` depending on *on_error*.

        Used by stuck-page detection so the caller can respect the error
        policy set at pagination startup.

        :return: Always ``True`` (stop iteration) when ``on_error='warn'``.
        :raises PaginationError: When ``on_error='raise'``.
        """
        if self._on_error == "raise":
            raise PaginationError(
                message,
                page=self.page,
                status_code=0,
                partial_items=self.collected,
            )
        logger.error("%s", message)
        return True

    def check_data(self, data: Any) -> bool:
        """Validate page data and detect stuck pagination.

        Must be called *before* yielding items.

        Valid falsy scalars (``0``, ``False``, ``""``) are treated as
        real data and do *not* terminate pagination.  Only ``None``,
        ``[]``, and ``{}`` are considered empty terminal responses.

        Stuck-page detection applies to **all** response types (list,
        dict, scalar).  If the same value is returned on successive
        pages beyond the threshold the method stops iteration.  When
        ``on_error='raise'`` a :exc:`PaginationError` is raised instead
        of silently stopping.

        Also detects alternating-page loops (A→B→A→B…) by keeping a
        short rolling window of recent page-data hashes.  The window
        catches patterns that reset the consecutive-repeat counter.

        Non-list responses (dict, scalar) are *not* paginated: the
        caller yields the value once and stops.  Stuck-page detection
        for non-list types therefore only fires if the same non-list
        value appears on the *first* two consecutive pages (i.e. the
        API is unexpectedly repeating non-paginated data).

        :return: ``True`` if iteration should stop.
        :raises PaginationError: When ``on_error='raise'`` and a stuck
            cycle is detected.
        """
        if data is None or data == [] or data == {}:
            return True

        # --- Consecutive identical-page detection (all types) ---
        if self._prev_data_set and data == self._prev_data:
            self._repeat_count += 1
            if self._repeat_count >= _REPEAT_THRESHOLD:
                return self._raise_or_stop(
                    f"Pagination aborted: page {self.page} returned identical "
                    f"data {self._repeat_count + 1} times consecutively"
                )
        else:
            self._repeat_count = 0
        self._prev_data = data
        self._prev_data_set = True

        if not isinstance(data, list):
            # Non-list responses are terminal (caller yields once and returns).
            # No window-based alternating detection needed for non-list types.
            return False

        # --- Alternating-page loop detection (rolling window, lists only) ---
        # Hash the page content and keep the last _WINDOW_SIZE hashes.
        # If the window is full and contains only two distinct values
        # that alternate perfectly, the pagination is stuck in a cycle.
        try:
            page_hash = hash(str(data))
        except Exception:
            page_hash = id(data)
        self._page_hash_window.append(page_hash)
        if len(self._page_hash_window) > _WINDOW_SIZE:
            self._page_hash_window.pop(0)
        if len(self._page_hash_window) == _WINDOW_SIZE:
            unique = set(self._page_hash_window)
            if len(unique) == 2:
                # Check that the window is a pure alternation (A,B,A,B,…)
                seq = self._page_hash_window
                if all(seq[i] != seq[i + 1] for i in range(len(seq) - 1)):
                    return self._raise_or_stop(
                        f"Pagination aborted: page {self.page} stuck in alternating "
                        f"loop (last {_WINDOW_SIZE} pages cycle between 2 distinct "
                        "responses)"
                    )

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
