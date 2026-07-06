"""Tests for the blesta_sdk.mcp package.

The mcp package requires Python >=3.10 and has optional extra dependencies.
All tests that exercise the FastMCP integration mock the mcp module entirely
so they run regardless of whether mcp is installed.
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module structure tests
# ---------------------------------------------------------------------------


def test_mcp_package_importable():
    import blesta_sdk.mcp

    assert blesta_sdk.mcp is not None


def test_mcp_server_importable():
    from blesta_sdk.mcp import server

    assert hasattr(server, "main")
    assert hasattr(server, "_build_server")


def test_mcp_tools_importable():
    from blesta_sdk.mcp import tools

    assert hasattr(tools, "register_tools")
    assert hasattr(tools, "TOOL_REGISTRY")


def test_mcp_resources_importable():
    from blesta_sdk.mcp import resources

    assert hasattr(resources, "register_resources")
    assert hasattr(resources, "RESOURCE_REGISTRY")
    assert hasattr(resources, "TEMPLATE_RESOURCE_REGISTRY")


def test_mcp_prompts_importable():
    from blesta_sdk.mcp import prompts

    assert hasattr(prompts, "register_prompts")
    assert hasattr(prompts, "PROMPT_REGISTRY")


def test_mcp_schemas_importable():
    from blesta_sdk.mcp import schemas

    assert hasattr(schemas, "_build_client")
    assert hasattr(schemas, "_creds_from_env")


# ---------------------------------------------------------------------------
# TOOL_REGISTRY and RESOURCE_REGISTRY contents
# ---------------------------------------------------------------------------

_REQUIRED_TOOLS = {
    "blesta_call",
    "blesta_get_all",
    "blesta_extract",
    "blesta_count",
    "blesta_get_report",
    "blesta_get_report_series",
    "blesta_list_models",
    "blesta_list_methods",
    "blesta_get_method_spec",
    "blesta_capabilities_report",
}

_REQUIRED_RESOURCES = {
    "blesta://schema/core",
    "blesta://schema/plugin",
    "blesta://models",
    "blesta://capabilities/markdown",
    "blesta://capabilities/json",
}

_REQUIRED_TEMPLATE_RESOURCES = {
    "blesta://models/{model}",
    "blesta://models/{model}/methods/{method}",
}


def test_all_required_tools_registered():
    from blesta_sdk.mcp.tools import TOOL_REGISTRY

    names = {entry[0] for entry in TOOL_REGISTRY}
    assert names >= _REQUIRED_TOOLS, f"Missing tools: {_REQUIRED_TOOLS - names}"


def test_all_required_resources_registered():
    from blesta_sdk.mcp.resources import RESOURCE_REGISTRY, TEMPLATE_RESOURCE_REGISTRY

    uris = {entry[0] for entry in RESOURCE_REGISTRY}
    template_uris = {entry[0] for entry in TEMPLATE_RESOURCE_REGISTRY}
    assert uris >= _REQUIRED_RESOURCES
    assert template_uris >= _REQUIRED_TEMPLATE_RESOURCES


def test_all_required_prompts_registered():
    from blesta_sdk.mcp.prompts import PROMPT_REGISTRY

    names = {entry[0] for entry in PROMPT_REGISTRY}
    expected = {
        "blesta_audit_client",
        "blesta_plan_migration",
        "blesta_reconcile_invoices",
        "blesta_extract_customer_snapshot",
        "blesta_map_to_prime_account",
    }
    assert expected <= names


# ---------------------------------------------------------------------------
# Real FastMCP boot (requires the mcp package; skipped where it is absent)
# ---------------------------------------------------------------------------


async def test_build_server_boots_with_real_fastmcp():
    """Construct the real server to catch startup/signature regressions.

    The other MCP tests mock the ``mcp`` module, so they never exercise the real
    ``FastMCP`` constructor — which is why an unsupported ``version=`` kwarg once
    shipped and broke ``blesta-mcp`` on boot with no failing test. This builds the
    actual server (registering all tools, resources, and prompts) and verifies the
    expected tools are present.
    """
    pytest.importorskip("mcp")
    from blesta_sdk.mcp.server import _build_server

    server = _build_server()
    tools = await server.list_tools()
    names = {tool.name for tool in tools}
    assert names >= _REQUIRED_TOOLS, f"Missing tools: {_REQUIRED_TOOLS - names}"


# ---------------------------------------------------------------------------
# Tool handler unit tests (no mcp required)
# ---------------------------------------------------------------------------

_CREDS = {
    "BLESTA_API_URL": "https://example.com/api",
    "BLESTA_API_USER": "user",
    "BLESTA_API_KEY": "key",
}


def _mock_response(data=None, status_code=200, is_csv=False, csv_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.data = data
    resp.is_csv = is_csv
    resp.csv_data = csv_data
    resp.errors.return_value = {"error": "bad"} if status_code != 200 else None
    return resp


def test_call_handler_success(capsys):
    from blesta_sdk.mcp.tools import _call_handler

    mock_resp = _mock_response(data={"id": 1})
    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.mcp.tools._build_client") as mock_build,
    ):
        mock_build.return_value.submit.return_value = mock_resp
        result = _call_handler("Clients", "getList", "{}", "GET")

    data = json.loads(result)
    assert data["ok"] is True
    assert data["data"] == {"id": 1}


def test_call_handler_inferred_method():
    from blesta_sdk.mcp.tools import _call_handler

    mock_resp = _mock_response(data=[{"id": 1}])
    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.mcp.tools._build_client") as mock_build,
    ):
        mock_build.return_value.call.return_value = mock_resp
        result = _call_handler("Clients", "getList")

    data = json.loads(result)
    assert data["ok"] is True


def test_call_handler_non200():
    from blesta_sdk.mcp.tools import _call_handler

    mock_resp = _mock_response(status_code=403)
    mock_resp.errors.return_value = {"error": "forbidden"}
    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.mcp.tools._build_client") as mock_build,
    ):
        mock_build.return_value.submit.return_value = mock_resp
        result = _call_handler("Clients", "getList", "{}", "GET")

    data = json.loads(result)
    assert data["ok"] is False


def test_get_all_handler():
    from blesta_sdk.mcp.tools import _get_all_handler

    rows = [{"id": 1}, {"id": 2}]
    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.mcp.tools._build_client") as mock_build,
    ):
        mock_build.return_value.get_all.return_value = rows
        result = _get_all_handler("Clients", "getList")

    data = json.loads(result)
    assert data["ok"] is True
    assert data["count"] == 2
    assert data["data"] == rows


def test_extract_handler():
    from blesta_sdk.mcp.tools import _extract_handler

    expected = {"Clients.getList": [{"id": 1}]}
    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.mcp.tools._build_client") as mock_build,
    ):
        mock_build.return_value.extract.return_value = expected
        result = _extract_handler('[["Clients", "getList"]]')

    data = json.loads(result)
    assert data["ok"] is True
    assert data["data"] == expected


def test_count_handler():
    from blesta_sdk.mcp.tools import _count_handler

    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.mcp.tools._build_client") as mock_build,
    ):
        mock_build.return_value.count.return_value = 42
        result = _count_handler("Clients")

    data = json.loads(result)
    assert data["ok"] is True
    assert data["count"] == 42


def test_get_report_handler_csv():
    from blesta_sdk.mcp.tools import _get_report_handler

    mock_resp = _mock_response(is_csv=True, csv_data=[{"col": "val"}])
    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.mcp.tools._build_client") as mock_build,
    ):
        mock_build.return_value.get_report.return_value = mock_resp
        result = _get_report_handler("package_revenue", "2025-01-01", "2025-01-31")

    data = json.loads(result)
    assert data["ok"] is True
    assert data["data"] == [{"col": "val"}]


def test_get_report_handler_error():
    from blesta_sdk.mcp.tools import _get_report_handler

    mock_resp = _mock_response(status_code=500)
    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.mcp.tools._build_client") as mock_build,
    ):
        mock_build.return_value.get_report.return_value = mock_resp
        result = _get_report_handler("package_revenue", "2025-01-01", "2025-01-31")

    data = json.loads(result)
    assert data["ok"] is False


def test_get_report_series_handler():
    from blesta_sdk.mcp.tools import _get_report_series_handler

    rows = [{"_period": "2025-01", "col": "val"}]
    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.mcp.tools._build_client") as mock_build,
    ):
        mock_build.return_value.get_report_series.return_value = rows
        result = _get_report_series_handler("package_revenue", "2025-01", "2025-03")

    data = json.loads(result)
    assert data["ok"] is True
    assert data["count"] == 1


def test_list_models_handler():
    from blesta_sdk.mcp.tools import _list_models_handler

    result = _list_models_handler()
    data = json.loads(result)
    assert data["ok"] is True
    assert isinstance(data["models"], list)
    assert len(data["models"]) > 0


def test_list_methods_handler():
    from blesta_sdk.mcp.tools import _list_methods_handler

    result = _list_methods_handler("Clients")
    data = json.loads(result)
    assert data["ok"] is True
    assert "getList" in data["methods"]


def test_list_methods_handler_unknown():
    from blesta_sdk.mcp.tools import _list_methods_handler

    result = _list_methods_handler("NonExistentModel999")
    data = json.loads(result)
    assert data["ok"] is False
    assert "not found" in data["error"]


def test_get_method_spec_handler():
    from blesta_sdk.mcp.tools import _get_method_spec_handler

    result = _get_method_spec_handler("Clients", "getList")
    data = json.loads(result)
    assert data["ok"] is True
    assert data["model"] == "Clients"
    assert data["method"] == "getList"


def test_get_method_spec_handler_unknown():
    from blesta_sdk.mcp.tools import _get_method_spec_handler

    result = _get_method_spec_handler("Clients", "nonExistent999")
    data = json.loads(result)
    assert data["ok"] is False


def test_capabilities_report_handler_markdown():
    from blesta_sdk.mcp.tools import _capabilities_report_handler

    result = _capabilities_report_handler("markdown")
    assert "# Blesta API" in result


def test_capabilities_report_handler_json():
    from blesta_sdk.mcp.tools import _capabilities_report_handler

    result = _capabilities_report_handler("json")
    data = json.loads(result)
    assert isinstance(data, list)


def test_discovery_handlers_use_cached_singleton():
    """Discovery handlers must reuse the lru-cached discovery (#100), not build a
    fresh BlestaDiscovery and reparse the 1.3MB schema on every call."""
    from blesta_sdk.discovery import registry
    from blesta_sdk.mcp import tools

    with patch.object(registry, "_get_discovery", wraps=registry._get_discovery) as spy:
        tools._list_models_handler()
        tools._list_methods_handler("Clients")
        tools._get_method_spec_handler("Clients", "getList")
    assert spy.call_count == 3
    # The cache returns the same instance rather than reparsing.
    assert registry._get_discovery() is registry._get_discovery()


# ---------------------------------------------------------------------------
# Resource handler unit tests
# ---------------------------------------------------------------------------


def test_schema_core_handler():
    from blesta_sdk.mcp.resources import _schema_core_handler

    result = _schema_core_handler()
    data = json.loads(result)
    assert "models" in data


def test_schema_plugin_handler():
    from blesta_sdk.mcp.resources import _schema_plugin_handler

    result = _schema_plugin_handler()
    data = json.loads(result)
    assert isinstance(data, dict)


def test_models_handler():
    from blesta_sdk.mcp.resources import _models_handler

    result = _models_handler()
    models = json.loads(result)
    assert isinstance(models, list)
    assert len(models) > 0


def test_model_handler():
    from blesta_sdk.mcp.resources import _model_handler

    result = _model_handler("Clients")
    data = json.loads(result)
    assert data["model"] == "Clients"
    assert "methods" in data


def test_model_handler_unknown():
    from blesta_sdk.mcp.resources import _model_handler

    result = _model_handler("NonExistentModel999")
    data = json.loads(result)
    assert "error" in data


def test_method_handler():
    from blesta_sdk.mcp.resources import _method_handler

    result = _method_handler("Clients", "getList")
    data = json.loads(result)
    assert data["model"] == "Clients"
    assert data["method"] == "getList"


def test_method_handler_unknown():
    from blesta_sdk.mcp.resources import _method_handler

    result = _method_handler("Clients", "nonExistent999")
    data = json.loads(result)
    assert "error" in data


def test_capabilities_markdown_handler():
    from blesta_sdk.mcp.resources import _capabilities_markdown_handler

    result = _capabilities_markdown_handler()
    assert "Blesta" in result


def test_capabilities_json_handler():
    from blesta_sdk.mcp.resources import _capabilities_json_handler

    result = _capabilities_json_handler()
    data = json.loads(result)
    assert isinstance(data, list)


# ---------------------------------------------------------------------------
# schemas._creds_from_env tests
# ---------------------------------------------------------------------------


def test_creds_from_env_success():
    from blesta_sdk.mcp.schemas import _creds_from_env

    with patch.dict(os.environ, _CREDS):
        url, user, key = _creds_from_env()
    assert url == "https://example.com/api"
    assert user == "user"
    assert key == "key"


def test_creds_from_env_missing():
    from blesta_sdk.mcp.schemas import _creds_from_env

    with (
        patch.dict(os.environ, {}, clear=True),
        pytest.raises(RuntimeError, match="Missing Blesta API credentials"),
    ):
        _creds_from_env()


# ---------------------------------------------------------------------------
# Server build test with mocked mcp
# ---------------------------------------------------------------------------


def test_build_server_missing_mcp():
    """_build_server raises ImportError when mcp is not installed."""
    from blesta_sdk.mcp.server import _build_server

    mods = {"mcp": None, "mcp.server": None, "mcp.server.fastmcp": None}
    with (
        patch.dict(sys.modules, mods),
        pytest.raises(ImportError, match="mcp package"),
    ):
        _build_server()


def test_build_server_with_mock_mcp():
    """_build_server builds successfully when mcp is mocked."""
    from blesta_sdk.mcp.server import _build_server

    mock_fastmcp_cls = MagicMock()
    mock_fastmcp_instance = MagicMock()
    mock_fastmcp_cls.return_value = mock_fastmcp_instance

    mock_fastmcp_module = MagicMock()
    mock_fastmcp_module.FastMCP = mock_fastmcp_cls

    mock_mcp_module = MagicMock()
    mock_mcp_server_module = MagicMock()

    with patch.dict(
        sys.modules,
        {
            "mcp": mock_mcp_module,
            "mcp.server": mock_mcp_server_module,
            "mcp.server.fastmcp": mock_fastmcp_module,
        },
    ):
        server = _build_server()

    assert server is mock_fastmcp_instance
    # Verify FastMCP was instantiated with the server name
    mock_fastmcp_cls.assert_called_once()
    call_kwargs = mock_fastmcp_cls.call_args
    name_arg = call_kwargs[0][0] if call_kwargs[0] else call_kwargs.kwargs.get("name")
    assert name_arg == "blesta-sdk"


def test_register_tools_calls_tool_decorator():
    """register_tools calls server.tool() for each tool."""
    from blesta_sdk.mcp.tools import TOOL_REGISTRY, register_tools

    mock_server = MagicMock()
    register_tools(mock_server)
    assert mock_server.tool.call_count == len(TOOL_REGISTRY)


def test_register_resources_calls_resource_decorator():
    """register_resources calls server.resource() for each resource."""
    from blesta_sdk.mcp.resources import (
        RESOURCE_REGISTRY,
        TEMPLATE_RESOURCE_REGISTRY,
        register_resources,
    )

    mock_server = MagicMock()
    register_resources(mock_server)
    expected = len(RESOURCE_REGISTRY) + len(TEMPLATE_RESOURCE_REGISTRY)
    assert mock_server.resource.call_count == expected


def test_register_prompts_calls_prompt_decorator():
    """register_prompts calls server.prompt() for each prompt."""
    from blesta_sdk.mcp.prompts import PROMPT_REGISTRY, register_prompts

    mock_server = MagicMock()
    register_prompts(mock_server)
    assert mock_server.prompt.call_count == len(PROMPT_REGISTRY)


# ---------------------------------------------------------------------------
# schemas._build_client tests
# ---------------------------------------------------------------------------


def test_build_client_returns_blesta_request():
    """_build_client creates a BlestaRequest from env creds."""
    from blesta_sdk.mcp.schemas import _build_client

    with patch.dict(os.environ, _CREDS):
        client = _build_client()

    from blesta_sdk.core.client import BlestaRequest

    assert isinstance(client, BlestaRequest)


def test_build_client_caches_per_config():
    """Repeated calls with the same config reuse one client/session (#101)."""
    from blesta_sdk.mcp import schemas

    schemas._reset_client_cache()
    with patch.dict(os.environ, _CREDS):
        first = schemas._build_client()
        second = schemas._build_client()
    assert first is second


def test_build_client_kwargs_bypass_cache():
    """Calls passing extra kwargs are not cached (may vary per call)."""
    from blesta_sdk.mcp import schemas

    schemas._reset_client_cache()
    with patch.dict(os.environ, _CREDS):
        a = schemas._build_client(timeout=5)
        b = schemas._build_client(timeout=5)
    assert a is not b


def test_build_client_respects_auth_method():
    """_build_client passes BLESTA_AUTH_METHOD to BlestaRequest."""
    from blesta_sdk.mcp.schemas import _build_client

    env = {**_CREDS, "BLESTA_AUTH_METHOD": "header"}
    with patch.dict(os.environ, env):
        client = _build_client()

    assert client.auth_method == "header"


def test_build_client_respects_allow_http():
    """_build_client passes BLESTA_ALLOW_HTTP=true to BlestaRequest."""
    from blesta_sdk.mcp.schemas import _build_client

    env = {
        **_CREDS,
        "BLESTA_API_URL": "http://example.com/api",
        "BLESTA_ALLOW_HTTP": "true",
    }
    with (
        patch.dict(os.environ, env),
        patch("blesta_sdk.mcp.schemas.BlestaRequest") as mock_req,
    ):
        _build_client()

    call_kwargs = mock_req.call_args
    assert call_kwargs.kwargs.get("allow_http") is True


# ---------------------------------------------------------------------------
# server.main() tests
# ---------------------------------------------------------------------------


def test_main_runs_server():
    """main() calls _build_server() and mcp_server.run()."""
    from blesta_sdk.mcp.server import main

    mock_server = MagicMock()
    with (
        patch("blesta_sdk.mcp.server._build_server", return_value=mock_server),
        patch("dotenv.load_dotenv"),
    ):
        main()

    mock_server.run.assert_called_once()


def test_main_no_dotenv():
    """main() proceeds normally when dotenv is not installed."""
    from blesta_sdk.mcp.server import main

    mock_server = MagicMock()
    with (
        patch("blesta_sdk.mcp.server._build_server", return_value=mock_server),
        patch.dict(sys.modules, {"dotenv": None}),
    ):
        main()

    mock_server.run.assert_called_once()


# ---------------------------------------------------------------------------
# tools._get_report_handler non-CSV path
# ---------------------------------------------------------------------------


def test_get_report_handler_json_data():
    """_get_report_handler returns ok=True with data when response is not CSV."""
    from blesta_sdk.mcp.tools import _get_report_handler

    mock_resp = _mock_response(data={"rows": [1, 2, 3]}, is_csv=False)
    with (
        patch.dict(os.environ, _CREDS),
        patch("blesta_sdk.mcp.tools._build_client") as mock_build,
    ):
        mock_build.return_value.get_report.return_value = mock_resp
        result = _get_report_handler("package_revenue", "2025-01-01", "2025-01-31")

    data = json.loads(result)
    assert data["ok"] is True
    assert data["data"] == {"rows": [1, 2, 3]}


# ---------------------------------------------------------------------------
# Tool error handling: missing credentials → structured JSON error
# ---------------------------------------------------------------------------


def test_call_handler_missing_creds_returns_json_error():
    """_call_handler returns ok=False JSON when credentials are missing."""
    from blesta_sdk.mcp.tools import _call_handler

    with patch.dict(os.environ, {}, clear=True):
        result = _call_handler("Clients", "getList")

    data = json.loads(result)
    assert data["ok"] is False
    assert "error" in data
    assert "BLESTA_API" in data["error"]


def test_get_all_handler_missing_creds_returns_json_error():
    """_get_all_handler returns ok=False JSON when credentials are missing."""
    from blesta_sdk.mcp.tools import _get_all_handler

    with patch.dict(os.environ, {}, clear=True):
        result = _get_all_handler("Clients", "getList")

    data = json.loads(result)
    assert data["ok"] is False
    assert "error" in data


def test_extract_handler_missing_creds_returns_json_error():
    """_extract_handler returns ok=False JSON when credentials are missing."""
    from blesta_sdk.mcp.tools import _extract_handler

    with patch.dict(os.environ, {}, clear=True):
        result = _extract_handler('[["Clients", "getList"]]')

    data = json.loads(result)
    assert data["ok"] is False
    assert "error" in data


def test_count_handler_missing_creds_returns_json_error():
    """_count_handler returns ok=False JSON when credentials are missing."""
    from blesta_sdk.mcp.tools import _count_handler

    with patch.dict(os.environ, {}, clear=True):
        result = _count_handler("Clients")

    data = json.loads(result)
    assert data["ok"] is False
    assert "error" in data


def test_get_report_handler_missing_creds_returns_json_error():
    """_get_report_handler returns ok=False JSON when credentials are missing."""
    from blesta_sdk.mcp.tools import _get_report_handler

    with patch.dict(os.environ, {}, clear=True):
        result = _get_report_handler("package_revenue", "2025-01-01", "2025-01-31")

    data = json.loads(result)
    assert data["ok"] is False
    assert "error" in data


def test_get_report_series_handler_missing_creds_returns_json_error():
    """_get_report_series_handler returns ok=False JSON when credentials are missing."""
    from blesta_sdk.mcp.tools import _get_report_series_handler

    with patch.dict(os.environ, {}, clear=True):
        result = _get_report_series_handler("package_revenue", "2025-01", "2025-03")

    data = json.loads(result)
    assert data["ok"] is False
    assert "error" in data


# ---------------------------------------------------------------------------
# server.main() ImportError → clean stderr exit
# ---------------------------------------------------------------------------


def test_main_import_error_exits_cleanly(capsys):
    """main() exits with code 1 and prints clean error when mcp not installed."""
    from blesta_sdk.mcp.server import main

    with (
        patch(
            "blesta_sdk.mcp.server._build_server",
            side_effect=ImportError("blesta-mcp requires the mcp package."),
        ),
        pytest.raises(SystemExit) as exc_info,
    ):
        main()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "blesta-mcp requires the mcp package" in captured.err


# ---------------------------------------------------------------------------
# Prompt write-safety: all prompts must include a safety note
# ---------------------------------------------------------------------------


def test_all_prompts_have_write_safety_note():
    """Every prompt template must contain a read-only or write-safety note."""
    from blesta_sdk.mcp.prompts import PROMPT_REGISTRY

    safety_terms = [
        "read-only",
        "do not",
        "not provide idempotency",
        "deduplication",
        "ledger",
        "not attempt",
        "confirm",
    ]
    for name, template, _desc in PROMPT_REGISTRY:
        lower = template.lower()
        has_note = any(term in lower for term in safety_terms)
        assert has_note, (
            f"Prompt {name!r} is missing a write-safety note. "
            f"Add a 'Note:' section with safety guidance."
        )


# ---------------------------------------------------------------------------
# blesta_call description includes mutation warning
# ---------------------------------------------------------------------------


def test_blesta_call_description_mentions_mutation():
    """blesta_call tool description must mention mutation idempotency risk."""
    from blesta_sdk.mcp.tools import TOOL_REGISTRY

    call_entry = next(e for e in TOOL_REGISTRY if e[0] == "blesta_call")
    desc = call_entry[2].lower()
    assert "idempotent" in desc or "mutation" in desc or "deduplication" in desc
