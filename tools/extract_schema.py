"""Extract a structured JSON schema from the Blesta source documentation.

Parses the phpDocumentor-generated HTML at https://source-docs.blesta.com/
to produce a machine-readable catalog of all API models, methods, parameters,
and return types.

Usage::

    uv run python tools/extract_schema.py
    uv run python tools/extract_schema.py --output schemas/custom.json
    uv run python tools/extract_schema.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

from tools._classify import INFERENCE_SOURCE, classify_category, infer_http_method

logger = logging.getLogger(__name__)

BASE_URL = "https://source-docs.blesta.com"
MODELS_URL = f"{BASE_URL}/packages/blesta-app-models.html"
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent.parent / "schemas" / "blesta_api_schema.json"
)
SCHEMA_VERSION = "2.0.0"


# ---------------------------------------------------------------------------
# Pure parsing functions (no I/O, testable with mocked HTML)
# ---------------------------------------------------------------------------


def parse_model_list(html: str) -> list[dict[str, str]]:
    """Extract model names and URLs from the package listing page.

    :param html: Raw HTML of the blesta-app-models page.
    :return: List of dicts with ``name`` and ``url`` keys.
    """
    soup = BeautifulSoup(html, "lxml")
    content = soup.find("div", class_="phpdocumentor-content")
    if not content:
        logger.warning("Could not find phpdocumentor-content div")
        return []

    models = []
    for a in content.find_all("a"):
        href = a.get("href", "")
        if "classes/" in href:
            name = a.get_text(strip=True)
            url = f"{BASE_URL}/{href}" if not href.startswith("http") else href
            models.append({"name": name, "url": url})
    return models


def parse_class_page(html: str) -> dict[str, Any]:
    """Extract all public methods from a class documentation page.

    Skips ``__construct`` methods.

    :param html: Raw HTML of a class page.
    :return: Dict mapping method names to their parsed details.
    """
    soup = BeautifulSoup(html, "lxml")
    methods: dict[str, Any] = {}

    articles = soup.find_all(
        "article", class_=lambda c: c and "-method" in c and "-public" in c
    )

    for article in articles:
        h4 = article.find("h4", id=lambda x: x and x.startswith("method_"))
        if not h4:
            continue

        method_id = h4["id"]
        method_name = method_id.replace("method_", "", 1)

        if method_name == "__construct":
            continue

        try:
            method_data = _parse_method_article(article, method_name)
            methods[method_name] = method_data
        except Exception:
            logger.warning("Failed to parse method %s", method_name, exc_info=True)

    return methods


def _parse_method_article(article: Tag, method_name: str) -> dict[str, Any]:
    """Parse a single method article element.

    :param article: The ``<article>`` BeautifulSoup tag for the method.
    :param method_name: Name of the method.
    :return: Dict with method details.
    """
    # Description
    summary_p = article.find("p", class_="phpdocumentor-summary")
    description = summary_p.get_text(strip=True) if summary_p else ""

    # Signature
    sig_code = article.find("code", class_="phpdocumentor-signature")
    signature = _extract_signature_text(sig_code) if sig_code else ""

    # Return type from signature
    return_type = ""
    response_span = (
        sig_code.find("span", class_="phpdocumentor-signature__response_type")
        if sig_code
        else None
    )
    if response_span:
        return_type = response_span.get_text(strip=True)

    # Parameters
    params = _parse_params(article, sig_code)

    # Return description (with optional sub-fields)
    return_description, return_fields = _parse_return_description(article)

    entry: dict[str, Any] = {
        "category": classify_category(method_name),
        "description": description,
        "http_method": infer_http_method(method_name),
        "params": params,
        "return_description": return_description,
        "return_type": return_type,
        "signature": signature,
    }

    if return_fields:
        entry["return_fields"] = return_fields

    return entry


def _extract_signature_text(sig_code: Tag) -> str:
    """Build a clean text signature from the code element.

    :param sig_code: The ``<code class="phpdocumentor-signature">`` tag.
    :return: Flattened signature string.
    """
    raw = sig_code.get_text()
    # Collapse whitespace and clean up
    parts = raw.split()
    sig = " ".join(parts)
    # Normalize spacing around punctuation
    for char in ["(", ")", "[", "]", ",", ":", "="]:
        sig = sig.replace(f" {char} ", f" {char} ")
    # Remove double spaces
    while "  " in sig:
        sig = sig.replace("  ", " ")
    return sig.strip()


def _parse_params(article: Tag, sig_code: Tag | None) -> list[dict[str, Any]]:
    """Parse the Parameters section of a method article.

    Uses the signature's bracket notation to determine required vs optional.

    :param article: The method ``<article>`` tag.
    :param sig_code: The signature ``<code>`` tag (for optional detection).
    :return: List of parameter dicts.
    """
    # Build a set of optional param names from the signature brackets
    optional_names: set[str] = set()
    if sig_code:
        for arg_span in sig_code.find_all(
            "span", class_="phpdocumentor-signature__argument"
        ):
            # If the arg_span contains a "[" bracket, it's optional
            text = arg_span.get_text()
            if "[" in text:
                name_span = arg_span.find(
                    "span", class_="phpdocumentor-signature__argument__name"
                )
                if name_span:
                    optional_names.add(name_span.get_text(strip=True).lstrip("$"))

    # Find the Parameters dl
    params_heading = None
    for h5 in article.find_all("h5"):
        if "Parameters" in h5.get_text():
            params_heading = h5
            break

    if not params_heading:
        return []

    dl = params_heading.find_next_sibling("dl", class_="phpdocumentor-argument-list")
    if not dl:
        return []

    params = []
    dts = dl.find_all("dt", class_="phpdocumentor-argument-list__entry")
    dds = dl.find_all("dd", class_="phpdocumentor-argument-list__definition")

    for dt, dd in zip(dts, dds):
        param = _parse_single_param(dt, dd, optional_names)
        if param:
            params.append(param)

    return params


def _parse_single_param(
    dt: Tag, dd: Tag, optional_names: set[str]
) -> dict[str, Any] | None:
    """Parse a single parameter dt/dd pair.

    :param dt: The ``<dt>`` tag.
    :param dd: The ``<dd>`` tag.
    :param optional_names: Set of parameter names known to be optional.
    :return: Parameter dict, or None on failure.
    """
    name_span = dt.find("span", class_="phpdocumentor-signature__argument__name")
    type_span = dt.find("span", class_="phpdocumentor-signature__argument__return-type")

    if not name_span:
        return None

    name = name_span.get_text(strip=True).lstrip("$")
    param_type = type_span.get_text(strip=True) if type_span else ""

    # Default value
    default_span = dt.find(
        "span", class_="phpdocumentor-signature__argument__default-value"
    )
    default = default_span.get_text(strip=True) if default_span else None

    # Description and sub-fields
    desc_section = dd.find("section", class_="phpdocumentor-description")
    param_description, fields = _extract_description_fields(desc_section)

    required = name not in optional_names

    result: dict[str, Any] = {
        "name": name,
        "type": param_type,
        "required": required,
        "default": default,
        "description": param_description,
    }

    if fields:
        result["fields"] = fields

    return result


def _extract_description_fields(
    desc_section: Tag | None,
) -> tuple[str, list[dict[str, str]]]:
    """Extract description text and structured sub-fields from a description section.

    If the section contains a ``<ul>`` with ``<li>`` items, each item is parsed
    as a sub-field (``name description`` split on first whitespace). The summary
    description comes from the ``<p>`` element before the list.

    :param desc_section: A ``<section class="phpdocumentor-description">`` tag,
        or ``None``.
    :return: Tuple of (description_text, list_of_field_dicts).
    """
    if not desc_section:
        return "", []

    ul = desc_section.find("ul")
    if not ul:
        return desc_section.get_text(strip=True), []

    fields: list[dict[str, str]] = []
    for li in ul.find_all("li", recursive=False):
        text = li.get_text(strip=True)
        parts = text.split(None, 1)
        if parts:
            fields.append(
                {
                    "name": parts[0],
                    "description": parts[1] if len(parts) > 1 else "",
                }
            )

    # Summary = first <p> before the <ul>
    p = desc_section.find("p")
    description = p.get_text(strip=True) if p else ""

    return description, fields


def _parse_return_description(
    article: Tag,
) -> tuple[str, list[dict[str, str]]]:
    """Extract the return value description from a method article.

    :param article: The method ``<article>`` tag.
    :return: Tuple of (return_description, return_fields).
    """
    for h5 in article.find_all("h5"):
        if "Return values" in h5.get_text():
            desc = h5.find_next_sibling("section", class_="phpdocumentor-description")
            if desc:
                return _extract_description_fields(desc)
    return "", []


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


def build_schema(
    models_html: str,
    fetch_fn: Any,
) -> dict[str, Any]:
    """Build the full schema from the models listing page.

    :param models_html: HTML of the models listing page.
    :param fetch_fn: Callable that takes a URL and returns HTML text.
    :return: Complete schema dict.
    """
    model_list = parse_model_list(models_html)
    logger.info("Found %d models", len(model_list))

    models: dict[str, Any] = {}
    total_methods = 0

    for model_info in model_list:
        name = model_info["name"]
        url = model_info["url"]
        try:
            class_html = fetch_fn(url)
            methods = parse_class_page(class_html)
            if methods:
                model_entry: dict[str, Any] = {
                    "methods": methods,
                    "url": url,
                }
                pagination = _detect_pagination(methods)
                if pagination:
                    model_entry["pagination"] = pagination
                models[name] = model_entry
                total_methods += len(methods)
                logger.info("  %s: %d methods", name, len(methods))
            else:
                logger.warning("  %s: no public methods found, skipping", name)
        except Exception:
            logger.warning("Failed to fetch/parse %s", name, exc_info=True)

    schema = {
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
            "schema_version": SCHEMA_VERSION,
            "source_type": "phpdocumentor_html",
            "source_url": MODELS_URL,
            "total_methods": total_methods,
        },
        "models": dict(sorted(models.items())),
    }
    return schema


def main() -> None:
    """CLI entry point for schema extraction."""
    parser = argparse.ArgumentParser(
        description="Extract Blesta API schema from source documentation"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output JSON file path (default: schemas/blesta_api_schema.json)",
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
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    import requests

    session = requests.Session()
    session.headers.update({"User-Agent": "blesta-sdk-schema-extractor/1.0"})

    models_html = fetch_with_delay(MODELS_URL, session, delay=args.delay)

    def fetch_fn(url: str) -> str:
        return fetch_with_delay(url, session, delay=args.delay)

    schema = build_schema(models_html, fetch_fn)

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
                    "model_names": sorted(schema["models"].keys()),
                },
                indent=2,
            )
        )
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(schema, f, indent=2, sort_keys=True)
        f.write("\n")

    logger.info("Schema written to %s", args.output)


if __name__ == "__main__":
    main()
