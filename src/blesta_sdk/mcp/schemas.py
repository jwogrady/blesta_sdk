"""Input schema helpers for MCP tool parameters.

These are plain dataclasses / typed dicts to keep the schema definitions
independent of whether pydantic is available.
"""

from __future__ import annotations

import os
from typing import Any

from blesta_sdk.core.client import BlestaRequest

#: Cache of clients keyed by resolved configuration. The MCP server is
#: long-lived and handles many tool calls; reusing one client per config keeps
#: HTTP connection pooling alive instead of discarding a Session per call.
_CLIENT_CACHE: dict[tuple[str, str, str, str, bool], BlestaRequest] = {}


def _reset_client_cache() -> None:
    """Clear the cached clients. Primarily for tests."""
    _CLIENT_CACHE.clear()


def _creds_from_env() -> tuple[str, str, str]:
    """Read API credentials from environment variables.

    :return: Tuple of (url, user, key).
    :raises RuntimeError: If any credential is missing.
    """
    url = os.getenv("BLESTA_API_URL", "")
    user = os.getenv("BLESTA_API_USER", "")
    key = os.getenv("BLESTA_API_KEY", "")
    missing = [
        name for name, val in [("URL", url), ("USER", user), ("KEY", key)] if not val
    ]
    if missing:
        raise RuntimeError(
            "Missing Blesta API credentials: "
            f"BLESTA_API_{', BLESTA_API_'.join(missing)}"
        )
    return url, user, key


def _build_client(**kwargs: Any) -> Any:
    """Return a :class:`~blesta_sdk.core.client.BlestaRequest` from env creds.

    Clients are cached per resolved configuration so repeated MCP tool calls
    reuse one client (and its pooled HTTP session) rather than opening a new
    connection each time. Calls that pass extra *kwargs* are never cached, since
    those may vary per call.

    :param kwargs: Extra kwargs forwarded to :class:`BlestaRequest`.
    :return: Configured client instance.
    """
    url, user, key = _creds_from_env()
    auth_method = os.getenv("BLESTA_AUTH_METHOD", "basic").strip().lower()
    allow_http = os.getenv("BLESTA_ALLOW_HTTP", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if kwargs:
        return BlestaRequest(
            url,
            user,
            key,
            auth_method=auth_method,
            allow_http=allow_http,
            **kwargs,
        )
    cache_key = (url, user, key, auth_method, allow_http)
    client = _CLIENT_CACHE.get(cache_key)
    if client is None:
        client = BlestaRequest(
            url,
            user,
            key,
            auth_method=auth_method,
            allow_http=allow_http,
        )
        _CLIENT_CACHE[cache_key] = client
    return client
