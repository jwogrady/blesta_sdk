"""Python SDK and CLI for the Blesta billing platform REST API."""

from ._client import BlestaRequest
from ._response import BlestaResponse

__all__ = ["BlestaRequest", "BlestaResponse", "AsyncBlestaRequest", "__version__"]


def __getattr__(name: str):
    if name == "AsyncBlestaRequest":
        try:
            from ._async_client import AsyncBlestaRequest
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
