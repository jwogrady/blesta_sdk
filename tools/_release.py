"""Locate and read a Blesta release (directory, zip, or zip URL).

Shared by both schema extractors when parsing PHP source directly from a
Blesta release instead of the published documentation. Release files are
only ever read as text — nothing from the release is executed.
"""

from __future__ import annotations

import json
import logging
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CLASS_PATTERN = re.compile(r"^\s*(?:final\s+|abstract\s+)?class\s+(\w+)", re.MULTILINE)


def resolve_release(source: str, fetch_bytes: Any = None) -> Path:
    """Resolve a release source to the Blesta root directory.

    :param source: A directory, a ``.zip`` file path, or an ``http(s)`` URL
        to a release zip.
    :param fetch_bytes: Callable taking a URL and returning bytes; required
        when ``source`` is a URL.
    :return: Path to the directory containing ``app/models``.
    :raises FileNotFoundError: If no Blesta root can be found.
    """
    if source.startswith(("http://", "https://")):
        if fetch_bytes is None:
            raise ValueError("fetch_bytes is required for URL sources")
        work = Path(tempfile.mkdtemp(prefix="blesta-release-"))
        zip_path = work / "release.zip"
        zip_path.write_bytes(fetch_bytes(source))
        return _extract_zip(zip_path, work / "extracted")

    path = Path(source)
    if path.is_file() and zipfile.is_zipfile(path):
        work = Path(tempfile.mkdtemp(prefix="blesta-release-"))
        return _extract_zip(path, work)
    return find_blesta_root(path)


def _extract_zip(zip_path: Path, dest: Path) -> Path:
    """Extract a release zip and locate its Blesta root.

    :param zip_path: Path to the zip archive.
    :param dest: Directory to extract into.
    :return: Path to the Blesta root inside ``dest``.
    """
    with zipfile.ZipFile(zip_path) as zf:
        root = dest.resolve()
        for member in zf.namelist():
            # Reject path traversal entries before extracting anything.
            if not (root / member).resolve().is_relative_to(root):
                raise ValueError(f"Unsafe path in release zip: {member}")
        zf.extractall(root)
    return find_blesta_root(dest)


def find_blesta_root(path: Path) -> Path:
    """Find the Blesta root (the directory containing ``app/models``).

    Checks ``path`` itself, then one and two levels below it, since release
    zips nest the install under a ``blesta/`` directory.

    :param path: Directory to search.
    :return: The Blesta root directory.
    :raises FileNotFoundError: If no ``app/models`` directory is found.
    """
    candidates = [path, *sorted(path.glob("*")), *sorted(path.glob("*/*"))]
    for candidate in candidates:
        if (candidate / "app" / "models").is_dir():
            return candidate
    raise FileNotFoundError(f"No Blesta release (app/models) found under {path}")


def read_release_version(root: Path) -> str | None:
    """Read the Blesta version from the release's signed ``manifest.json``.

    :param root: Blesta root directory.
    :return: Version string (e.g. ``"6.0.4"``) or None if unavailable.
    """
    try:
        data = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("No readable manifest.json in %s", root)
        return None
    version = data.get("version") if isinstance(data, dict) else None
    return version if isinstance(version, str) else None


def read_plugin_version(plugin_dir: Path) -> str | None:
    """Read a plugin's version from its ``config.json``.

    :param plugin_dir: Plugin directory (e.g. ``plugins/order``).
    :return: Version string or None if unavailable.
    """
    try:
        data = json.loads((plugin_dir / "config.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    version = data.get("version") if isinstance(data, dict) else None
    return version if isinstance(version, str) else None


def read_php_class(path: Path) -> tuple[str | None, str]:
    """Read a PHP file and return its class name and source.

    :param path: Path to the PHP file.
    :return: Tuple of (class name or None if no class is declared, source).
        Encoded files have no readable class declaration.
    """
    source = path.read_text(encoding="utf-8", errors="replace")
    match = _CLASS_PATTERN.search(source)
    return (match.group(1) if match else None), source
