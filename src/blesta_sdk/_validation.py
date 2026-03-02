"""Internal input validation helpers.

This module is not part of the public API and may change without notice.
"""

from __future__ import annotations


def validate_segment(segment: str, name: str) -> None:
    """Validate a URL path segment (model or method name).

    Rejects segments that could escape the API path via scheme
    injection, path traversal, netloc override, or backslash tricks.
    Allows plugin dot notation (e.g. ``"plugin.model"``).

    :param segment: The path segment to validate.
    :param name: Human-readable label for error messages (e.g. ``"model"``).
    :raises ValueError: If the segment is unsafe.
    """
    if not segment:
        raise ValueError(f"{name} cannot be empty")
    if "://" in segment:
        raise ValueError(f"{name} cannot contain scheme")
    if segment.startswith("//"):
        raise ValueError(f"{name} cannot start with '//'")
    if segment.startswith("/"):
        raise ValueError(f"{name} cannot start with '/'")
    if ".." in segment:
        raise ValueError(f"{name} cannot contain '..'")
    if "\\" in segment:
        raise ValueError(f"{name} cannot contain backslashes")
