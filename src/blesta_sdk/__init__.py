"""Python SDK and CLI for the Blesta billing platform REST API."""

from ._client import BlestaRequest
from ._response import BlestaResponse

__all__ = ["BlestaRequest", "BlestaResponse", "__version__"]


def _get_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("blesta_sdk")
    except PackageNotFoundError:
        return "unknown"


__version__ = _get_version()
del _get_version
