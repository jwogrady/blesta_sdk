from importlib.metadata import version, PackageNotFoundError

from . import api, cli, core

__all__ = ["api", "cli", "core"]

try:
    __version__ = version("blesta_sdk")
except PackageNotFoundError:
    __version__ = "unknown"
