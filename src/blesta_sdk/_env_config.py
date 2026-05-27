"""Environment-keyed configuration for dev / stage / live Blesta deployments.

Provides :class:`BlestaEnvConfig` which resolves credentials from constructor
keyword arguments first, then falls back to environment variables of the form
``BLESTA_{ENV}_URL``, ``BLESTA_{ENV}_USER``, and ``BLESTA_{ENV}_KEY`` — where
``{ENV}`` is the upper-cased environment name (``DEV``, ``STAGE``, or
``LIVE``).

There is **no fallback between environments**: credentials for ``live`` are
never read when ``stage`` is requested, and so on.

Usage::

    from blesta_sdk import BlestaEnvConfig

    cfg = BlestaEnvConfig("stage")
    client = cfg.client()
    resp = client.submit("GET", "clients", "list")
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from ._client import BlestaRequest

_VALID_ENVS = ("dev", "stage", "live")
_EnvLiteral = Literal["dev", "stage", "live"]


class BlestaEnvConfig:
    """Resolve Blesta credentials for a named environment and create a client.

    :param env: One of ``"dev"``, ``"stage"``, or ``"live"``.
    :param url: API base URL.  If omitted, read from ``BLESTA_{ENV}_URL``.
    :param user: API user.  If omitted, read from ``BLESTA_{ENV}_USER``.
    :param key: API key.  If omitted, read from ``BLESTA_{ENV}_KEY``.
    :raises ValueError: If *env* is not one of the three valid values, or if
        any credential cannot be resolved.
    """

    def __init__(
        self,
        env: _EnvLiteral,
        *,
        url: str | None = None,
        user: str | None = None,
        key: str | None = None,
    ) -> None:
        if env not in _VALID_ENVS:
            raise ValueError(f"env must be one of {_VALID_ENVS!r}, got {env!r}")
        self._env = env
        prefix = f"BLESTA_{env.upper()}"

        self._url = url or os.environ.get(f"{prefix}_URL") or ""
        self._user = user or os.environ.get(f"{prefix}_USER") or ""
        self._key = key or os.environ.get(f"{prefix}_KEY") or ""

        missing: list[str] = []
        if not self._url:
            missing.append(f"{prefix}_URL")
        if not self._user:
            missing.append(f"{prefix}_USER")
        if not self._key:
            missing.append(f"{prefix}_KEY")

        if missing:
            raise ValueError(
                f"Missing required configuration for env={env!r}: " + ", ".join(missing)
            )

    @property
    def env(self) -> str:
        """The environment name (``'dev'``, ``'stage'``, or ``'live'``)."""
        return self._env

    @property
    def url(self) -> str:
        """Resolved API base URL."""
        return self._url

    @property
    def user(self) -> str:
        """Resolved API user."""
        return self._user

    def client(self, **kwargs: Any) -> BlestaRequest:
        """Construct and return a :class:`~blesta_sdk.BlestaRequest` for this env.

        Any keyword arguments are forwarded to :class:`~blesta_sdk.BlestaRequest`
        (e.g. ``retry_mutations=True``, ``allow_http=True``).

        :return: A configured :class:`~blesta_sdk.BlestaRequest` instance.
        """
        from ._client import BlestaRequest

        return BlestaRequest(
            url=self._url,
            user=self._user,
            key=self._key,
            **kwargs,
        )

    def __repr__(self) -> str:  # pragma: no cover
        return f"BlestaEnvConfig(env={self._env!r}, url={self._url!r})"
