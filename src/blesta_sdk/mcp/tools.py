"""MCP tool registrations for the Blesta SDK server.

All tool handlers are thin adapters over :mod:`blesta_sdk.core` and
:mod:`blesta_sdk.discovery`.  Business logic lives in the SDK, not here.

Credentials are resolved from environment variables at call time so the
same server process can serve different environments by restarting with
different env vars.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from blesta_sdk.mcp.schemas import _build_client  # re-exported for test patching

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool handler functions (registered by register_tools)
# ---------------------------------------------------------------------------


def _call_handler(
    model: str,
    method: str,
    params: str = "{}",
    action: str | None = None,
) -> str:
    """Invoke a single Blesta API method.

    HTTP method is inferred from the bundled schema when *action* is omitted.
    Pass ``action="POST"``, ``"PUT"``, or ``"DELETE"`` explicitly for mutating
    operations.  Mutations are **not idempotent** — the caller is responsible
    for deduplication and ledger tracking.

    :param model: API model name (e.g. ``"Clients"``).
    :param method: API method name (e.g. ``"getList"``).
    :param params: JSON string of request parameters.
    :param action: HTTP method override (GET/POST/PUT/DELETE).
    :return: JSON-serialised response data.
    """
    try:
        args: dict[str, Any] = json.loads(params) if params else {}
        client = _build_client()
        if action:
            response = client.submit(model, method, args, action.upper())
        else:
            response = client.call(model, method, args)
        if response.status_code == 200:
            return json.dumps({"ok": True, "data": response.data})
        return json.dumps({"ok": False, "errors": response.errors()})
    except Exception as exc:
        logger.debug("_call_handler error: %s", exc)
        return json.dumps({"ok": False, "error": str(exc)})


def _get_all_handler(
    model: str,
    method: str,
    params: str = "{}",
    max_pages: int | None = None,
) -> str:
    """Paginate a Blesta list method and return all records.

    :param model: API model name.
    :param method: API method name.
    :param params: JSON string of request parameters.
    :param max_pages: Optional page limit.
    :return: JSON-serialised list of all records.
    """
    try:
        args: dict[str, Any] = json.loads(params) if params else {}
        client = _build_client()
        rows = client.get_all(model, method, args or None, max_pages=max_pages)
        return json.dumps({"ok": True, "count": len(rows), "data": rows})
    except Exception as exc:
        logger.debug("_get_all_handler error: %s", exc)
        return json.dumps({"ok": False, "error": str(exc)})


def _extract_handler(
    targets: str,
) -> str:
    """Fetch multiple paginated endpoints.

    :param targets: JSON array of ``[model, method]`` or ``[model, method, params]``
        tuples.
    :return: JSON-serialised dict mapping ``model.method`` to record lists.
    """
    try:
        target_list = json.loads(targets)
        client = _build_client()
        results = client.extract([tuple(t) for t in target_list])  # type: ignore[arg-type]
        return json.dumps({"ok": True, "data": results})
    except Exception as exc:
        logger.debug("_extract_handler error: %s", exc)
        return json.dumps({"ok": False, "error": str(exc)})


def _count_handler(
    model: str,
    method: str = "getListCount",
    params: str = "{}",
) -> str:
    """Fetch a record count from a Blesta count method.

    :param model: API model name.
    :param method: Count method name.
    :param params: JSON string of request parameters.
    :return: JSON-serialised count.
    """
    try:
        args: dict[str, Any] = json.loads(params) if params else {}
        client = _build_client()
        count = client.count(model, method, args or None)
        return json.dumps({"ok": True, "count": count})
    except Exception as exc:
        logger.debug("_count_handler error: %s", exc)
        return json.dumps({"ok": False, "error": str(exc)})


def _get_report_handler(
    report_type: str,
    start_date: str,
    end_date: str,
    extra_vars: str = "{}",
) -> str:
    """Fetch a Blesta report.

    :param report_type: Report type (e.g. ``"package_revenue"``).
    :param start_date: Start date as ``"YYYY-MM-DD"``.
    :param end_date: End date as ``"YYYY-MM-DD"``.
    :param extra_vars: JSON string of additional vars[] parameters.
    :return: JSON-serialised report rows (CSV parsed) or raw data.
    """
    try:
        extra: dict[str, str] = json.loads(extra_vars) if extra_vars else {}
        client = _build_client()
        response = client.get_report(report_type, start_date, end_date, extra or None)
        if response.status_code != 200:
            return json.dumps({"ok": False, "error": f"HTTP {response.status_code}"})
        if response.is_csv:
            return json.dumps({"ok": True, "data": response.csv_data or []})
        return json.dumps({"ok": True, "data": response.data})
    except Exception as exc:
        logger.debug("_get_report_handler error: %s", exc)
        return json.dumps({"ok": False, "error": str(exc)})


def _get_report_series_handler(
    report_type: str,
    start_month: str,
    end_month: str,
    extra_vars: str = "{}",
) -> str:
    """Fetch monthly reports as a flat row list.

    :param report_type: Report type.
    :param start_month: Start month as ``"YYYY-MM"``.
    :param end_month: End month as ``"YYYY-MM"``.
    :param extra_vars: JSON string of additional vars[] parameters.
    :return: JSON-serialised list of row dicts with ``_period`` key.
    """
    try:
        extra: dict[str, str] = json.loads(extra_vars) if extra_vars else {}
        client = _build_client()
        rows = client.get_report_series(
            report_type, start_month, end_month, extra or None
        )
        return json.dumps({"ok": True, "count": len(rows), "data": rows})
    except Exception as exc:
        logger.debug("_get_report_series_handler error: %s", exc)
        return json.dumps({"ok": False, "error": str(exc)})


def _list_models_handler(source: str | None = None) -> str:
    """List all available API model names.

    :param source: Filter by ``"core"`` or ``"plugin"``; ``None`` for all.
    :return: JSON-serialised list of model names.
    """
    from blesta_sdk.discovery.registry import _get_discovery

    disco = _get_discovery()
    models = disco.list_models(source=source)
    return json.dumps({"ok": True, "models": models})


def _list_methods_handler(model: str) -> str:
    """List all method names for a model.

    :param model: Model name (e.g. ``"Clients"``).
    :return: JSON-serialised list of method names.
    """
    from blesta_sdk.discovery.registry import _get_discovery

    disco = _get_discovery()
    try:
        methods = disco.list_methods(model)
        return json.dumps({"ok": True, "model": model, "methods": methods})
    except KeyError:
        return json.dumps({"ok": False, "error": f"Model {model!r} not found"})


def _get_method_spec_handler(model: str, method: str) -> str:
    """Return the full spec for a model/method pair.

    :param model: Model name.
    :param method: Method name.
    :return: JSON-serialised :class:`~blesta_sdk.discovery.registry.MethodSpec`.
    """
    from blesta_sdk.discovery.registry import _get_discovery

    disco = _get_discovery()
    try:
        spec = disco.get_method_spec(model, method)
        return json.dumps(
            {
                "ok": True,
                "model": spec.model,
                "method": spec.method,
                "http_method": spec.http_method,
                "category": spec.category,
                "description": spec.description,
                "params": spec.params,
                "return_type": spec.return_type,
                "source": spec.source,
                "signature": spec.signature,
            }
        )
    except KeyError as exc:
        return json.dumps({"ok": False, "error": str(exc)})


def _capabilities_report_handler(output_format: str = "markdown") -> str:
    """Generate a capabilities report of the full API surface.

    :param output_format: ``"markdown"`` or ``"json"``.
    :return: Report string.
    """
    from blesta_sdk.discovery.registry import _get_discovery

    disco = _get_discovery()
    report = disco.generate_capabilities_report(output_format=output_format)  # type: ignore[arg-type]
    return report


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


#: Ordered list of (tool_name, handler, description) for registration.
TOOL_REGISTRY: list[tuple[str, Any, str]] = [
    (
        "blesta_call",
        _call_handler,
        (
            "Invoke a single Blesta API method. HTTP method is inferred from the "
            "schema when action is omitted. For mutations (POST/PUT/DELETE), pass "
            "action explicitly. Mutations are not idempotent — the caller is "
            "responsible for deduplication."
        ),
    ),
    (
        "blesta_get_all",
        _get_all_handler,
        "Paginate a Blesta list method and return all records as a list.",
    ),
    (
        "blesta_extract",
        _extract_handler,
        "Fetch multiple paginated endpoints in one call.",
    ),
    (
        "blesta_count",
        _count_handler,
        "Fetch a record count from a Blesta count method.",
    ),
    (
        "blesta_get_report",
        _get_report_handler,
        "Fetch a Blesta report for a specific date range.",
    ),
    (
        "blesta_get_report_series",
        _get_report_series_handler,
        "Fetch monthly reports across a date range as flat rows.",
    ),
    (
        "blesta_list_models",
        _list_models_handler,
        "List all available Blesta API models from the bundled schema.",
    ),
    (
        "blesta_list_methods",
        _list_methods_handler,
        "List all method names for a Blesta API model.",
    ),
    (
        "blesta_get_method_spec",
        _get_method_spec_handler,
        "Return the full spec (HTTP method, params, return type) for a model/method.",
    ),
    (
        "blesta_capabilities_report",
        _capabilities_report_handler,
        "Generate a full capabilities report of the Blesta API surface.",
    ),
]


def register_tools(mcp_server: Any) -> None:
    """Register all Blesta tools on *mcp_server*.

    :param mcp_server: A :class:`mcp.server.fastmcp.FastMCP` instance.
    """
    for name, handler, description in TOOL_REGISTRY:
        mcp_server.tool(name=name, description=description)(handler)
    logger.debug("Registered %d MCP tools", len(TOOL_REGISTRY))
