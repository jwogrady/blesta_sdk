"""Extract a structured JSON schema from Blesta plugin PHP source.

Parses phpDoc-annotated PHP model files to produce a machine-readable catalog
of plugin API methods, parameters, and return types. Two sources:

- ``--source``: every bundled plugin in a Blesta release (directory, zip, or
  zip URL). Covers plugins that are not on GitHub (e.g. support_manager,
  order) and records the release and plugin versions.
- default: the public ``blesta/plugin-*`` GitHub repositories listed in
  ``PLUGIN_REGISTRY``.

Usage::

    uv run python -m tools.extract_plugin_schema --source path/to/blesta-6.0.4.zip
    uv run python -m tools.extract_plugin_schema
    uv run python -m tools.extract_plugin_schema --output schemas/custom.json
    uv run python -m tools.extract_plugin_schema --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools._classify import INFERENCE_SOURCE, classify_category, infer_http_method
from tools._floor import (
    ExtractionFloorError,
    enforce_model_floor,
    previous_model_count,
)
from tools._release import (
    read_php_class,
    read_plugin_version,
    read_release_version,
    resolve_release,
)

logger = logging.getLogger(__name__)

RAW_GITHUB_BASE = "https://raw.githubusercontent.com/blesta"
GITHUB_BLOB_BASE = "https://github.com/blesta"
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "blesta_sdk"
    / "schemas"
    / "blesta_plugin_schema.json"
)
SCHEMA_VERSION = "2.0.0"

# Plugin name -> list of model file basenames (without .php)
PLUGIN_REGISTRY: dict[str, list[str]] = {
    "cms": ["cms_pages"],
    "domains": ["domains_domains", "domains_tlds"],
    "extension_generator": ["extension_generator_extensions"],
    "softaculous": ["softaculous_queued_services"],
    "webhooks": ["webhooks_events", "webhooks_logs", "webhooks_webhooks"],
}

# A docblock immediately followed by a function declaration. The docblock body
# must not contain "*/", otherwise a private method's docblock would be paired
# with the next public method. PHP attributes may sit between the two.
_METHOD_PATTERN = re.compile(
    r"/\*\*((?:(?!\*/).)*)\*/\s*"
    r"(?:#\[[^\]]*\]\s*)*"
    r"((?:(?:final|abstract|static|public|protected|private)\s+)*)"
    r"function\s+&?\s*(\w+)\s*\(",
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# Pure parsing functions (no I/O, testable with fixture strings)
# ---------------------------------------------------------------------------


def parse_php_file(source: str) -> dict[str, Any]:
    """Extract all public methods from a PHP model source file.

    Skips ``__construct``, private, and protected methods.
    Methods without a docblock are skipped.

    :param source: Raw PHP source code.
    :return: Dict mapping method names to their parsed details.
    """
    methods: dict[str, Any] = {}
    for docblock, method_name, param_str, return_hint in _extract_methods(source):
        try:
            entry = _build_method_entry(docblock, method_name, param_str, return_hint)
            methods[method_name] = entry
        except Exception:
            logger.warning("Failed to parse method %s", method_name, exc_info=True)
    return methods


def _extract_methods(
    source: str,
) -> list[tuple[str, str, str, str]]:
    """Find docblock + public function pairs in PHP source.

    Uses regex to find docblocks followed by public function declarations,
    then bracket-counting to extract the full parameter string (which may
    contain nested brackets in default values).

    :param source: Raw PHP source code.
    :return: List of (docblock_body, method_name, param_string, return_hint).
    """
    results: list[tuple[str, str, str, str]] = []

    for match in _METHOD_PATTERN.finditer(source):
        docblock_body = match.group(1)
        modifiers = match.group(2).split()
        method_name = match.group(3)

        # No visibility modifier means public in PHP.
        if "private" in modifiers or "protected" in modifiers:
            continue
        if method_name == "__construct":
            continue

        # Extract parameter string using bracket counting from the (
        open_pos = match.end() - 1  # position of the (
        param_str = _extract_balanced_parens(source, open_pos)

        # Look for return type hint after the closing )
        after_params = source[open_pos + len(param_str) + 2 :][:50]
        return_hint = ""
        hint_match = re.match(r"\s*:\s*([\w|?\\]+)", after_params)
        if hint_match:
            return_hint = hint_match.group(1)

        results.append((docblock_body, method_name, param_str, return_hint))

    return results


def _extract_balanced_parens(source: str, open_pos: int) -> str:
    """Extract content between balanced parentheses.

    :param source: Full source string.
    :param open_pos: Position of the opening ``(``.
    :return: Content between the parentheses (excluding the parens).
    """
    depth = 0
    i = open_pos
    while i < len(source):
        if source[i] == "(":
            depth += 1
        elif source[i] == ")":
            depth -= 1
            if depth == 0:
                return source[open_pos + 1 : i]
        i += 1
    return source[open_pos + 1 :]


def _parse_docblock(body: str) -> dict[str, Any]:
    """Parse a phpDoc block body into structured data.

    :param body: The text between ``/**`` and ``*/`` (without those markers).
    :return: Dict with ``summary``, ``params``, ``return_type``,
        ``return_description``.
    """
    # Clean lines: strip leading *, whitespace
    lines = []
    for raw_line in body.split("\n"):
        cleaned = raw_line.strip()
        if cleaned.startswith("*"):
            cleaned = cleaned[1:]
            if cleaned.startswith(" "):
                cleaned = cleaned[1:]
        lines.append(cleaned)

    # Extract summary: lines before the first @tag
    summary_lines: list[str] = []
    for line in lines:
        if line.startswith("@"):
            break
        stripped = line.strip()
        if stripped:
            summary_lines.append(stripped)

    summary = " ".join(summary_lines)

    # Rejoin for tag extraction
    full_text = "\n".join(lines)

    # Extract @param tags
    params: list[dict[str, Any]] = []
    param_pattern = re.compile(
        r"@param\s+([\w|?\\<>,\s]+?)\s+\$(\w+)\s*(.*?)(?=\n\s*@|\Z)",
        re.DOTALL,
    )
    for m in param_pattern.finditer(full_text):
        param_type = m.group(1).strip()
        param_name = m.group(2)
        raw_desc = m.group(3)
        param_desc, fields = _extract_sub_fields(raw_desc)
        entry: dict[str, Any] = {
            "name": param_name,
            "type": param_type,
            "description": param_desc,
        }
        if fields:
            entry["fields"] = fields
        params.append(entry)

    # Extract @return tag
    return_type = ""
    return_description = ""
    return_match = re.search(
        r"@return\s+([\w|?\\<>,\s]+?)\s+(.*?)(?=\n\s*@|\Z)",
        full_text,
        re.DOTALL,
    )
    if return_match:
        return_type = return_match.group(1).strip()
        return_description = _clean_description(return_match.group(2))
    else:
        # Try @return with just a type and no description
        return_match_simple = re.search(
            r"@return\s+([\w|?\\<>,]+)\s*$",
            full_text,
            re.MULTILINE,
        )
        if return_match_simple:
            return_type = return_match_simple.group(1).strip()

    return {
        "summary": summary,
        "params": params,
        "return_type": return_type,
        "return_description": return_description,
    }


def _clean_description(text: str) -> str:
    """Clean a multi-line description from a docblock tag.

    :param text: Raw description text possibly spanning multiple lines.
    :return: Cleaned description string.
    """
    lines = text.split("\n")
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            cleaned.append(stripped)
    return " ".join(cleaned)


def _extract_sub_fields(
    raw_desc: str,
) -> tuple[str, list[dict[str, str]]]:
    """Extract sub-field definitions from a raw docblock description.

    Lines starting with ``- `` (after stripping) are treated as sub-field
    definitions in the form ``- field_name Description text``. Remaining
    lines form the summary description.

    :param raw_desc: Raw description text from a ``@param`` tag.
    :return: Tuple of (cleaned_description, list_of_field_dicts).
    """
    desc_lines = raw_desc.split("\n")
    fields: list[dict[str, str]] = []
    summary_lines: list[str] = []

    for line in desc_lines:
        stripped = line.strip()
        if stripped.startswith("- ") and len(stripped) > 2:
            field_text = stripped[2:].strip()
            parts = field_text.split(None, 1)
            if parts:
                fields.append(
                    {
                        "name": parts[0],
                        "description": parts[1] if len(parts) > 1 else "",
                    }
                )
        else:
            summary_lines.append(line)

    description = _clean_description("\n".join(summary_lines))
    return description, fields


def _parse_param_string(param_str: str) -> list[dict[str, Any]]:
    """Parse a PHP function parameter string into structured data.

    Handles bracket-aware comma splitting for default values like
    ``['id' => 'asc']``.

    :param param_str: The content between ``(`` and ``)`` in a function sig.
    :return: List of param dicts with ``name``, ``type_hint``, ``default``.
    """
    param_str = param_str.strip()
    if not param_str:
        return []

    parts = _split_by_comma(param_str)
    params: list[dict[str, Any]] = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        param_data = _parse_single_php_param(part)
        if param_data:
            params.append(param_data)

    return params


def _split_by_comma(text: str) -> list[str]:
    """Split a string by commas, respecting nested brackets.

    :param text: String to split.
    :return: List of parts.
    """
    parts: list[str] = []
    depth = 0
    current: list[str] = []

    for char in text:
        if char in "([{":
            depth += 1
            current.append(char)
        elif char in ")]}":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)

    if current:
        parts.append("".join(current))

    return parts


def _parse_single_php_param(part: str) -> dict[str, Any] | None:
    """Parse a single PHP parameter declaration.

    Handles forms like:
    - ``int $id``
    - ``array $vars = []``
    - ``$page = 1``
    - ``?string $callback``
    - ``array $order = ['id' => 'asc']``

    :param part: A single parameter string.
    :return: Dict with ``name``, ``type_hint``, ``default``, or None.
    """
    # Split on = for default value (bracket-aware)
    default = None
    eq_pos = _find_top_level_eq(part)
    if eq_pos >= 0:
        default = part[eq_pos + 1 :].strip()
        part = part[:eq_pos].strip()

    # Match: [type] $name
    match = re.match(r"(.*?)\$(\w+)\s*$", part.strip())
    if not match:
        return None

    type_hint = match.group(1).strip()
    name = match.group(2)

    return {"name": name, "type_hint": type_hint, "default": default}


def _find_top_level_eq(text: str) -> int:
    """Find the position of the first top-level ``=`` in a parameter string.

    :param text: Parameter string.
    :return: Position of ``=``, or -1 if not found.
    """
    depth = 0
    for i, char in enumerate(text):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "=" and depth == 0:
            return i
    return -1


def _build_method_entry(
    docblock: str,
    method_name: str,
    param_str: str,
    return_hint: str,
) -> dict[str, Any]:
    """Build a schema method entry from parsed docblock and signature data.

    :param docblock: Raw docblock body text.
    :param method_name: Name of the method.
    :param param_str: Parameter string from the function signature.
    :param return_hint: Return type hint from the function signature.
    :return: Method entry dict matching the schema format.
    """
    doc_data = _parse_docblock(docblock)
    sig_params = _parse_param_string(param_str)

    # Build a lookup from docblock params by name
    doc_params_by_name: dict[str, dict[str, str]] = {}
    for dp in doc_data["params"]:
        doc_params_by_name[dp["name"]] = dp

    # Merge signature params with docblock info
    params: list[dict[str, Any]] = []
    for sp in sig_params:
        name = sp["name"]
        doc_param = doc_params_by_name.get(name, {})

        # Type: prefer docblock over signature hint
        param_type = doc_param.get("type", "") or sp.get("type_hint", "")

        # Required: no default value means required
        default = sp.get("default")
        required = default is None

        param_entry: dict[str, Any] = {
            "name": name,
            "type": param_type,
            "required": required,
            "default": default,
            "description": doc_param.get("description", ""),
        }

        # Carry over sub-fields from docblock if present
        doc_fields = doc_param.get("fields")
        if doc_fields:
            param_entry["fields"] = doc_fields

        params.append(param_entry)

    # Return type: prefer docblock, fall back to signature hint
    return_type = doc_data["return_type"] or return_hint

    # Build signature string
    signature = _build_signature(method_name, param_str, return_type)

    return {
        "category": classify_category(method_name),
        "description": doc_data["summary"],
        "http_method": infer_http_method(method_name),
        "params": params,
        "return_description": doc_data["return_description"],
        "return_type": return_type,
        "signature": signature,
    }


def _build_signature(method_name: str, param_str: str, return_type: str) -> str:
    """Build a clean signature string.

    :param method_name: Name of the method.
    :param param_str: Raw parameter string.
    :param return_type: Return type.
    :return: Signature string like ``public methodName(params) : type``.
    """
    # Normalize whitespace in param string
    param_normalized = " ".join(param_str.split())

    sig = f"public {method_name}({param_normalized})"
    if return_type:
        sig += f" : {return_type}"
    return sig


# ---------------------------------------------------------------------------
# I/O layer (orchestration, HTTP fetching, CLI)
# ---------------------------------------------------------------------------


def fetch_with_delay(url: str, session: Any, delay: float = 0.5) -> str:
    """Fetch a URL with a polite delay.

    :param url: URL to fetch.
    :param session: A ``requests.Session`` instance.
    :param delay: Seconds to wait after the request.
    :return: Response text.
    """
    logger.info("Fetching %s", url)
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    time.sleep(delay)
    return resp.text


def _fetch_bytes(url: str, session: Any) -> bytes:
    """Download a binary file (e.g. a release zip).

    :param url: URL to fetch.
    :param session: A ``requests.Session`` instance.
    :return: Response body.
    """
    logger.info("Downloading %s", url)
    resp = session.get(url, timeout=300)
    resp.raise_for_status()
    return resp.content


def _detect_pagination(methods: dict[str, Any]) -> dict[str, str]:
    """Detect getList/getListCount pagination pairs in a model's methods.

    :param methods: Dict of method names to method data.
    :return: Dict mapping list method names to their count method names.
    """
    pagination: dict[str, str] = {}
    method_names = set(methods.keys())
    for name in method_names:
        count_name = name + "Count"
        if count_name in method_names:
            pagination[name] = count_name
    return dict(sorted(pagination.items()))


def build_plugin_schema(fetch_fn: Any) -> dict[str, Any]:
    """Build the plugin schema by fetching and parsing all registered models.

    :param fetch_fn: Callable that takes a URL and returns text content.
    :return: Complete plugin schema dict.
    """
    models: dict[str, Any] = {}
    plugins_found: list[str] = []

    for plugin_name, model_names in sorted(PLUGIN_REGISTRY.items()):
        plugin_had_models = False

        for model_name in model_names:
            raw_url = (
                f"{RAW_GITHUB_BASE}/plugin-{plugin_name}"
                f"/master/models/{model_name}.php"
            )
            source_url = (
                f"{GITHUB_BLOB_BASE}/plugin-{plugin_name}"
                f"/blob/master/models/{model_name}.php"
            )
            model_key = f"{plugin_name}.{model_name}"

            try:
                php_source = fetch_fn(raw_url)
                methods = parse_php_file(php_source)
                if methods:
                    model_entry: dict[str, Any] = {
                        "methods": methods,
                        "source": source_url,
                    }
                    pagination = _detect_pagination(methods)
                    if pagination:
                        model_entry["pagination"] = pagination
                    models[model_key] = model_entry
                    plugin_had_models = True
                    logger.info("  %s: %d methods", model_key, len(methods))
                else:
                    logger.warning("  %s: no public methods found, skipping", model_key)
            except Exception:
                logger.warning("Failed to fetch/parse %s", model_key, exc_info=True)

        if plugin_had_models:
            plugins_found.append(plugin_name)

    return _assemble_schema(models, plugins_found, "github_php_docblocks")


def build_plugin_schema_from_release(root: Path) -> dict[str, Any]:
    """Build the plugin schema from every bundled plugin in a Blesta release.

    Each ``plugins/<name>/models/*.php`` file with a readable class and at
    least one documented public method becomes a ``<plugin>.<model>`` entry.

    :param root: Blesta root directory (contains ``plugins/``).
    :return: Complete plugin schema dict.
    """
    models: dict[str, Any] = {}
    plugins_found: list[str] = []
    plugin_versions: dict[str, str] = {}

    for plugin_dir in sorted((root / "plugins").iterdir()):
        model_dir = plugin_dir / "models"
        if not model_dir.is_dir():
            continue
        plugin_name = plugin_dir.name
        plugin_had_models = False

        for php_file in sorted(model_dir.glob("*.php")):
            class_name, php_source = read_php_class(php_file)
            if class_name is None:
                logger.warning("  %s: no readable class, skipping", php_file)
                continue
            methods = parse_php_file(php_source)
            if not methods:
                continue
            model_key = f"{plugin_name}.{php_file.stem}"
            if plugin_name in PLUGIN_REGISTRY:
                source = (
                    f"{GITHUB_BLOB_BASE}/plugin-{plugin_name}"
                    f"/blob/master/models/{php_file.name}"
                )
            else:
                source = f"plugins/{plugin_name}/models/{php_file.name}"
            model_entry: dict[str, Any] = {"methods": methods, "source": source}
            pagination = _detect_pagination(methods)
            if pagination:
                model_entry["pagination"] = pagination
            models[model_key] = model_entry
            plugin_had_models = True
            logger.info("  %s: %d methods", model_key, len(methods))

        if plugin_had_models:
            plugins_found.append(plugin_name)
            version = read_plugin_version(plugin_dir)
            if version:
                plugin_versions[plugin_name] = version

    schema = _assemble_schema(models, plugins_found, "release_php_docblocks")
    schema["metadata"]["blesta_version"] = read_release_version(root)
    schema["metadata"]["plugin_versions"] = plugin_versions
    return schema


def _assemble_schema(
    models: dict[str, Any], plugins_found: list[str], source_type: str
) -> dict[str, Any]:
    """Wrap extracted models with schema metadata.

    :param models: Model key -> model entry.
    :param plugins_found: Names of plugins that contributed models.
    :param source_type: Where the models were extracted from.
    :return: Complete plugin schema dict.
    """
    return {
        "metadata": {
            "extracted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "inference": {
                "category": {
                    "description": "Inferred from method name prefix patterns",
                    "source": INFERENCE_SOURCE,
                },
                "http_method": {
                    "description": "Inferred from method name prefix patterns",
                    "source": INFERENCE_SOURCE,
                },
            },
            "model_count": len(models),
            "plugins": sorted(plugins_found),
            "schema_version": SCHEMA_VERSION,
            "source_type": source_type,
            "total_methods": sum(len(m["methods"]) for m in models.values()),
        },
        "models": dict(sorted(models.items())),
    }


def main() -> None:
    """CLI entry point for plugin schema extraction."""
    parser = argparse.ArgumentParser(
        description="Extract Blesta plugin schema from PHP sources"
    )
    parser.add_argument(
        "--source",
        help=(
            "Blesta release directory, zip, or zip URL. Parses every bundled "
            "plugin. Without it, fetches PLUGIN_REGISTRY plugins from GitHub."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output JSON file path (default: schemas/blesta_plugin_schema.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and print stats without writing the file",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between HTTP requests in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--allow-shrink",
        action="store_true",
        help=(
            "Accept a model count below the floor set by the previous run "
            "(use only when models were genuinely removed upstream)"
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    import requests

    session = requests.Session()
    session.headers.update({"User-Agent": "blesta-sdk-plugin-schema-extractor/1.0"})

    def fetch_fn(url: str) -> str:
        return fetch_with_delay(url, session, delay=args.delay)

    # Same floor as the core extractor, for the same reason (issue #111): this
    # loop skips a model it cannot fetch or parse with a warning, so without an
    # assertion on the count a restructured upstream commits a hollow schema
    # from a green run. With no previous schema to compare against, the GitHub
    # mode falls back to the registry as its baseline — it is this tool's
    # declaration of what should be there, so a first run is not unfloored.
    # The floor also stops a GitHub-only run (PLUGIN_REGISTRY plugins) from
    # overwriting a fuller schema extracted from a release with --source.
    baseline = previous_model_count(args.output)
    if baseline is None and not args.source:
        baseline = sum(len(models) for models in PLUGIN_REGISTRY.values())

    try:
        if args.source:
            source = f"the plugins in the Blesta release at {args.source}"
            root = resolve_release(
                args.source, fetch_bytes=lambda u: _fetch_bytes(u, session)
            )
            schema = build_plugin_schema_from_release(root)
        else:
            source = "the Blesta plugin repositories in PLUGIN_REGISTRY"
            schema = build_plugin_schema(fetch_fn)
        enforce_model_floor(
            schema["metadata"]["model_count"],
            source=source,
            output=args.output,
            baseline=baseline,
            allow_shrink=args.allow_shrink,
        )
    except ExtractionFloorError as exc:
        logger.error("%s", exc)
        raise SystemExit(1) from exc

    logger.info(
        "Schema: %d models, %d total methods",
        schema["metadata"]["model_count"],
        schema["metadata"]["total_methods"],
    )

    if args.dry_run:
        print(
            json.dumps(
                {
                    "metadata": schema["metadata"],
                    "model_keys": sorted(schema["models"].keys()),
                },
                indent=2,
            )
        )
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        # Minified: the schema is parsed via json.loads at runtime (whitespace
        # is irrelevant), so drop indentation to keep the bundled file small.
        json.dump(schema, f, separators=(",", ":"), sort_keys=True)

    logger.info("Schema written to %s", args.output)


if __name__ == "__main__":
    main()
