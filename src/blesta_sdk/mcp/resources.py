"""MCP resource registrations for the Blesta SDK server.

Resources expose read-only data about the API schema and capabilities.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Resource handler functions
# ---------------------------------------------------------------------------


def _schema_core_handler() -> str:
    """Return the raw core API schema JSON.

    :return: JSON string of the core API schema.
    """
    try:
        from blesta_sdk.discovery.registry import _bundled_schema_text

        text = _bundled_schema_text("blesta_api_schema.json")
        return text or "{}"
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to load core schema: %s", exc)
        return "{}"


def _schema_plugin_handler() -> str:
    """Return the raw plugin schema JSON.

    :return: JSON string of the plugin schema.
    """
    try:
        from blesta_sdk.discovery.registry import _bundled_schema_text

        text = _bundled_schema_text("blesta_plugin_schema.json")
        return text or "{}"
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to load plugin schema: %s", exc)
        return "{}"


def _models_handler() -> str:
    """Return a list of all model names as JSON.

    :return: JSON-serialised list of model names.
    """
    import json

    from blesta_sdk.discovery.registry import BlestaDiscovery

    disco = BlestaDiscovery()
    return json.dumps(disco.list_models())


def _model_handler(model: str) -> str:
    """Return method names for a specific model.

    :param model: Model name.
    :return: JSON-serialised list of method names.
    """
    import json

    from blesta_sdk.discovery.registry import BlestaDiscovery

    disco = BlestaDiscovery()
    try:
        return json.dumps({"model": model, "methods": disco.list_methods(model)})
    except KeyError:
        return json.dumps({"error": f"Model {model!r} not found"})


def _method_handler(model: str, method: str) -> str:
    """Return the spec for a specific model/method.

    :param model: Model name.
    :param method: Method name.
    :return: JSON-serialised method spec.
    """
    import json

    from blesta_sdk.discovery.registry import BlestaDiscovery

    disco = BlestaDiscovery()
    try:
        spec = disco.get_method_spec(model, method)
        return json.dumps(
            {
                "model": spec.model,
                "method": spec.method,
                "http_method": spec.http_method,
                "description": spec.description,
                "params": spec.params,
                "return_type": spec.return_type,
            }
        )
    except KeyError as exc:
        return json.dumps({"error": str(exc)})


def _capabilities_markdown_handler() -> str:
    """Return the API capabilities report as Markdown.

    :return: Markdown string.
    """
    from blesta_sdk.discovery.registry import BlestaDiscovery

    return BlestaDiscovery().generate_capabilities_report("markdown")


def _capabilities_json_handler() -> str:
    """Return the API capabilities report as JSON.

    :return: JSON string.
    """
    from blesta_sdk.discovery.registry import BlestaDiscovery

    return BlestaDiscovery().generate_capabilities_report("json")


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


#: Ordered list of (uri_template, handler, description) for registration.
RESOURCE_REGISTRY: list[tuple[str, Any, str]] = [
    (
        "blesta://schema/core",
        _schema_core_handler,
        "Raw core Blesta API schema JSON.",
    ),
    (
        "blesta://schema/plugin",
        _schema_plugin_handler,
        "Raw Blesta plugin schema JSON.",
    ),
    (
        "blesta://models",
        _models_handler,
        "List of all available Blesta API model names.",
    ),
    (
        "blesta://capabilities/markdown",
        _capabilities_markdown_handler,
        "Blesta API capabilities report in Markdown.",
    ),
    (
        "blesta://capabilities/json",
        _capabilities_json_handler,
        "Blesta API capabilities report as JSON.",
    ),
]

#: Resources with URI template parameters (registered separately).
TEMPLATE_RESOURCE_REGISTRY: list[tuple[str, Any, str]] = [
    (
        "blesta://models/{model}",
        _model_handler,
        "Methods available for a specific Blesta API model.",
    ),
    (
        "blesta://models/{model}/methods/{method}",
        _method_handler,
        "Full spec for a specific Blesta API model/method.",
    ),
]


def register_resources(mcp_server: Any) -> None:
    """Register all Blesta resources on *mcp_server*.

    :param mcp_server: A :class:`mcp.server.fastmcp.FastMCP` instance.
    """
    for uri, handler, description in RESOURCE_REGISTRY:
        mcp_server.resource(uri, description=description)(handler)

    for uri_template, handler, description in TEMPLATE_RESOURCE_REGISTRY:
        mcp_server.resource(uri_template, description=description)(handler)

    total = len(RESOURCE_REGISTRY) + len(TEMPLATE_RESOURCE_REGISTRY)
    logger.debug("Registered %d MCP resources", total)
