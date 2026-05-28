"""Python SDK and CLI for the Blesta billing platform REST API."""

from blesta_sdk.core.client import BlestaRequest
from blesta_sdk.core.config import BlestaEnvConfig
from blesta_sdk.core.errors import (
    BlestaAPIError,
    BlestaAuthError,
    BlestaConnectionError,
    BlestaError,
    BlestaRateLimitError,
    BlestaServerError,
    PaginationError,
)
from blesta_sdk.core.response import BlestaResponse
from blesta_sdk.discovery.registry import BlestaDiscovery, MethodSpec

__all__ = [
    "AsyncBlestaRequest",
    "BlestaAPIError",
    "BlestaAuthError",
    "BlestaConnectionError",
    "BlestaDiscovery",
    "BlestaEnvConfig",
    "BlestaError",
    "BlestaRateLimitError",
    "BlestaRequest",
    "BlestaResponse",
    "BlestaServerError",
    "MethodSpec",
    "PaginationError",
    "__version__",
]


def __getattr__(name: str) -> object:
    if name == "AsyncBlestaRequest":
        try:
            from blesta_sdk.core.async_client import AsyncBlestaRequest
        except ImportError as err:
            raise ImportError(
                "AsyncBlestaRequest requires httpx. "
                "Install it with: pip install blesta_sdk[async]"
            ) from err
        return AsyncBlestaRequest
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _get_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("blesta_sdk")
    except PackageNotFoundError:
        return "unknown"


__version__ = _get_version()
del _get_version
