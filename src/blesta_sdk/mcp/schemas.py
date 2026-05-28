"""Input schema helpers for MCP tool parameters.

These are plain dataclasses / typed dicts to keep the schema definitions
independent of whether pydantic is available.
"""

from __future__ import annotations

import os
from typing import Any

from blesta_sdk.core.client import BlestaRequest


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
    """Create a :class:`~blesta_sdk.core.client.BlestaRequest` from env creds.

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
    return BlestaRequest(
        url,
        user,
        key,
        auth_method=auth_method,
        allow_http=allow_http,
        **kwargs,
    )
