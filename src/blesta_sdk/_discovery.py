"""API discovery module for Blesta schema introspection.

Loads machine-readable JSON schemas (core API and plugin) and exposes
methods for listing models, methods, resolving HTTP verbs, and
generating capability reports.

This module uses only the standard library. Schemas are loaded lazily
on first access.

Usage::

    from blesta_sdk._discovery import BlestaDiscovery

    disco = BlestaDiscovery()
    disco.list_models()
    disco.list_methods("Clients")
    disco.get_method_spec("Clients", "getList")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

_DEFAULT_CORE_SCHEMA = (
    Path(__file__).resolve().parent.parent.parent / "schemas" / "blesta_api_schema.json"
)
_DEFAULT_PLUGIN_SCHEMA = (
    Path(__file__).resolve().parent.parent.parent
    / "schemas"
    / "blesta_plugin_schema.json"
)


@dataclass(frozen=True)
class MethodSpec:
    """Specification for a single API method.

    :param model: Model name (e.g. ``"Clients"``).
    :param method: Method name (e.g. ``"getList"``).
    :param http_method: Inferred HTTP method, or ``None``.
    :param category: ``"api"`` or ``"internal"``.
    :param description: Summary description from the schema.
    :param params: List of parameter dicts from the schema.
    :param return_type: Return type string from the schema.
    :param return_description: Description of the return value.
    :param source: ``"core"`` or ``"plugin"``.
    :param signature: PHP-style signature string.
    """

    model: str
    method: str
    http_method: str | None
    category: str
    description: str
    params: list[dict[str, Any]] = field(default_factory=list)
    return_type: str = ""
    return_description: str = ""
    source: str = "core"
    signature: str = ""


class BlestaDiscovery:
    """Schema-driven API discovery for Blesta.

    Loads core and plugin schemas from JSON files and provides methods
    for introspecting the available API surface.

    :param core_schema_path: Path to the core API schema JSON.
        Defaults to the bundled ``schemas/blesta_api_schema.json``.
    :param plugin_schema_path: Path to the plugin schema JSON.
        Defaults to the bundled ``schemas/blesta_plugin_schema.json``.
    """

    def __init__(
        self,
        core_schema_path: str | Path | None = None,
        plugin_schema_path: str | Path | None = None,
    ) -> None:
        self._core_path = Path(core_schema_path) if core_schema_path else None
        self._plugin_path = Path(plugin_schema_path) if plugin_schema_path else None
        self._registry: dict[str, dict[str, Any]] | None = None
        self._source_map: dict[str, str] | None = None
        self._pagination_map: dict[str, dict[str, str]] | None = None

    def _ensure_loaded(self) -> None:
        """Load schemas lazily on first access."""
        if self._registry is not None:
            return

        self._registry = {}
        self._source_map = {}
        self._pagination_map = {}

        core_path = self._core_path or _DEFAULT_CORE_SCHEMA
        self._load_schema(core_path, "core")

        plugin_path = self._plugin_path or _DEFAULT_PLUGIN_SCHEMA
        self._load_schema(plugin_path, "plugin")

    def _load_schema(self, path: Path, source: str) -> None:
        """Load a single schema file into the registry.

        :param path: Path to the JSON schema file.
        :param source: Source label (``"core"`` or ``"plugin"``).
        """
        assert self._registry is not None
        assert self._source_map is not None
        assert self._pagination_map is not None

        try:
            with open(path) as f:
                data = json.load(f)
        except FileNotFoundError:
            logger.warning("Schema file not found: %s", path)
            return
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in schema file: %s", path)
            return

        models = data.get("models", {})
        for model_name, model_data in models.items():
            self._registry[model_name] = model_data
            self._source_map[model_name] = source
            pagination = model_data.get("pagination")
            if pagination:
                self._pagination_map[model_name] = pagination

    def list_models(self, source: str | None = None) -> list[str]:
        """List all available model names.

        :param source: Filter by source: ``"core"``, ``"plugin"``, or
            ``None`` for all.
        :return: Sorted list of model names.
        """
        self._ensure_loaded()
        assert self._registry is not None
        assert self._source_map is not None

        if source is None:
            return sorted(self._registry.keys())
        return sorted(name for name, src in self._source_map.items() if src == source)

    def list_methods(self, model: str) -> list[str]:
        """List all method names for a model.

        :param model: Model name (e.g. ``"Clients"``).
        :return: Sorted list of method names.
        :raises KeyError: If the model is not found.
        """
        self._ensure_loaded()
        assert self._registry is not None

        model_data = self._registry.get(model)
        if model_data is None:
            raise KeyError(f"Model {model!r} not found in schema")
        return sorted(model_data.get("methods", {}).keys())

    def get_method_spec(self, model: str, method: str) -> MethodSpec:
        """Get the full specification for a method.

        :param model: Model name (e.g. ``"Clients"``).
        :param method: Method name (e.g. ``"getList"``).
        :return: :class:`MethodSpec` dataclass.
        :raises KeyError: If the model or method is not found.
        """
        self._ensure_loaded()
        assert self._registry is not None
        assert self._source_map is not None

        model_data = self._registry.get(model)
        if model_data is None:
            raise KeyError(f"Model {model!r} not found in schema")

        methods = model_data.get("methods", {})
        method_data = methods.get(method)
        if method_data is None:
            raise KeyError(f"Method {method!r} not found in model {model!r}")

        return MethodSpec(
            model=model,
            method=method,
            http_method=method_data.get("http_method"),
            category=method_data.get("category", "api"),
            description=method_data.get("description", ""),
            params=method_data.get("params", []),
            return_type=method_data.get("return_type", ""),
            return_description=method_data.get("return_description", ""),
            source=self._source_map.get(model, "unknown"),
            signature=method_data.get("signature", ""),
        )

    def resolve_http_method(
        self,
        model: str,
        method: str,
        default: str = "POST",
    ) -> str:
        """Resolve the HTTP method for an API call.

        :param model: Model name.
        :param method: Method name.
        :param default: Fallback HTTP method if not found.
        :return: HTTP method string (``"GET"``, ``"POST"``, etc.).
        """
        self._ensure_loaded()
        assert self._registry is not None

        model_data = self._registry.get(model)
        if model_data is None:
            return default

        method_data = model_data.get("methods", {}).get(method)
        if method_data is None:
            return default

        return method_data.get("http_method") or default

    def suggest_pagination_pair(
        self, model: str, list_method: str = "getList"
    ) -> str | None:
        """Suggest the count method for a paginated list method.

        :param model: Model name.
        :param list_method: The list method name to find a count pair for.
        :return: The count method name, or ``None`` if no pair found.
        """
        self._ensure_loaded()
        assert self._pagination_map is not None

        pagination = self._pagination_map.get(model)
        if pagination is None:
            return None
        return pagination.get(list_method)

    def generate_capabilities_report(
        self,
        format: Literal["markdown", "json"] = "markdown",
    ) -> str:
        """Generate a capabilities report of the full API surface.

        :param format: Output format — ``"markdown"`` or ``"json"``.
        :return: Report string.
        """
        self._ensure_loaded()
        assert self._registry is not None
        assert self._source_map is not None

        report_data: list[dict[str, Any]] = []
        for model_name in sorted(self._registry.keys()):
            model_data = self._registry[model_name]
            methods = model_data.get("methods", {})
            api_methods = [
                name
                for name, data in sorted(methods.items())
                if data.get("category") == "api"
            ]
            report_data.append(
                {
                    "model": model_name,
                    "source": self._source_map.get(model_name, "unknown"),
                    "total_methods": len(methods),
                    "api_methods": len(api_methods),
                    "method_names": api_methods,
                }
            )

        if format == "json":
            return json.dumps(report_data, indent=2, sort_keys=True)

        # Markdown
        lines = ["# Blesta API Capabilities Report", ""]
        total_models = len(report_data)
        total_api = sum(m["api_methods"] for m in report_data)
        lines.append(f"**{total_models} models**, **{total_api} API methods**")
        lines.append("")

        for entry in report_data:
            source_tag = f" ({entry['source']})" if entry["source"] != "core" else ""
            lines.append(f"## {entry['model']}{source_tag}")
            lines.append("")
            for method_name in entry["method_names"]:
                lines.append(f"- `{method_name}`")
            lines.append("")

        return "\n".join(lines)

    def generate_ai_index(self, path: str | Path) -> int:
        """Generate a JSONL index file for AI embeddings.

        Each line is a JSON object with model, method, description,
        http_method, params, and return_type fields — suitable for
        embedding pipelines.

        :param path: Output file path.
        :return: Number of entries written.
        """
        self._ensure_loaded()
        assert self._registry is not None
        assert self._source_map is not None

        count = 0
        with open(path, "w") as f:
            for model_name in sorted(self._registry.keys()):
                model_data = self._registry[model_name]
                for method_name, method_data in sorted(
                    model_data.get("methods", {}).items()
                ):
                    if method_data.get("category") != "api":
                        continue
                    entry = {
                        "model": model_name,
                        "method": method_name,
                        "source": self._source_map.get(model_name, "unknown"),
                        "http_method": method_data.get("http_method"),
                        "description": method_data.get("description", ""),
                        "params": [
                            p.get("name", "") for p in method_data.get("params", [])
                        ],
                        "return_type": method_data.get("return_type", ""),
                    }
                    f.write(json.dumps(entry, sort_keys=True) + "\n")
                    count += 1
        return count
