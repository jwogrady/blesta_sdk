"""Tests for BlestaDiscovery — schema-driven API introspection."""

import json

import pytest

from blesta_sdk import BlestaDiscovery, MethodSpec

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CORE_SCHEMA = {
    "metadata": {
        "schema_version": "2.0.0",
        "model_count": 2,
        "total_methods": 5,
    },
    "models": {
        "Clients": {
            "methods": {
                "getList": {
                    "category": "api",
                    "description": "Get a list of clients",
                    "http_method": "GET",
                    "params": [
                        {
                            "name": "status",
                            "type": "string",
                            "required": False,
                            "default": "null",
                            "description": "Filter by status",
                        }
                    ],
                    "return_type": "array",
                    "return_description": "A list of client objects",
                    "signature": "public getList(string $status = null) : array",
                },
                "getListCount": {
                    "category": "api",
                    "description": "Get total number of clients",
                    "http_method": "GET",
                    "params": [],
                    "return_type": "int",
                    "return_description": "The total count",
                    "signature": "public getListCount() : int",
                },
                "create": {
                    "category": "api",
                    "description": "Create a new client",
                    "http_method": "POST",
                    "params": [
                        {
                            "name": "vars",
                            "type": "array",
                            "required": True,
                            "default": None,
                            "description": "Client data",
                        }
                    ],
                    "return_type": "int",
                    "return_description": "The client ID",
                    "signature": "public create(array $vars) : int",
                },
                "validateCreation": {
                    "category": "internal",
                    "description": "Validate client creation input",
                    "http_method": None,
                    "params": [],
                    "return_type": "bool",
                    "return_description": "",
                    "signature": "",
                },
            },
            "pagination": {"getList": "getListCount"},
        },
        "Invoices": {
            "methods": {
                "getList": {
                    "category": "api",
                    "description": "Get a list of invoices",
                    "http_method": "GET",
                    "params": [],
                    "return_type": "array",
                    "return_description": "A list of invoices",
                    "signature": "public getList() : array",
                },
            },
        },
    },
}

PLUGIN_SCHEMA = {
    "metadata": {
        "schema_version": "2.0.0",
        "model_count": 1,
        "plugins": ["cms"],
        "total_methods": 2,
    },
    "models": {
        "cms.cms_pages": {
            "methods": {
                "add": {
                    "category": "api",
                    "description": "Add a CMS page",
                    "http_method": "POST",
                    "params": [],
                    "return_type": "void",
                    "return_description": "",
                    "signature": "public add(array $vars)",
                },
                "getList": {
                    "category": "api",
                    "description": "Get CMS pages",
                    "http_method": "GET",
                    "params": [],
                    "return_type": "array",
                    "return_description": "",
                    "signature": "public getList() : array",
                },
            },
        },
    },
}


@pytest.fixture
def schema_dir(tmp_path):
    """Create temp schema files and return (core_path, plugin_path)."""
    core_path = tmp_path / "core.json"
    plugin_path = tmp_path / "plugin.json"
    core_path.write_text(json.dumps(CORE_SCHEMA))
    plugin_path.write_text(json.dumps(PLUGIN_SCHEMA))
    return core_path, plugin_path


@pytest.fixture
def disco(schema_dir):
    """BlestaDiscovery loaded with test schemas."""
    core_path, plugin_path = schema_dir
    return BlestaDiscovery(
        core_schema_path=core_path,
        plugin_schema_path=plugin_path,
    )


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------


def test_list_models_all(disco):
    models = disco.list_models()
    assert models == ["Clients", "Invoices", "cms.cms_pages"]


def test_list_models_core_only(disco):
    models = disco.list_models(source="core")
    assert models == ["Clients", "Invoices"]


def test_list_models_plugin_only(disco):
    models = disco.list_models(source="plugin")
    assert models == ["cms.cms_pages"]


def test_list_models_unknown_source(disco):
    models = disco.list_models(source="nonexistent")
    assert models == []


# ---------------------------------------------------------------------------
# list_methods
# ---------------------------------------------------------------------------


def test_list_methods(disco):
    methods = disco.list_methods("Clients")
    assert methods == ["create", "getList", "getListCount", "validateCreation"]


def test_list_methods_unknown_model(disco):
    with pytest.raises(KeyError, match="not found"):
        disco.list_methods("NonExistent")


# ---------------------------------------------------------------------------
# get_method_spec
# ---------------------------------------------------------------------------


def test_get_method_spec(disco):
    spec = disco.get_method_spec("Clients", "getList")
    assert isinstance(spec, MethodSpec)
    assert spec.model == "Clients"
    assert spec.method == "getList"
    assert spec.http_method == "GET"
    assert spec.category == "api"
    assert spec.description == "Get a list of clients"
    assert spec.return_type == "array"
    assert spec.source == "core"
    assert len(spec.params) == 1
    assert spec.params[0]["name"] == "status"


def test_get_method_spec_plugin(disco):
    spec = disco.get_method_spec("cms.cms_pages", "add")
    assert spec.source == "plugin"
    assert spec.http_method == "POST"


def test_get_method_spec_internal(disco):
    spec = disco.get_method_spec("Clients", "validateCreation")
    assert spec.category == "internal"
    assert spec.http_method is None


def test_get_method_spec_unknown_model(disco):
    with pytest.raises(KeyError, match="Model.*not found"):
        disco.get_method_spec("Unknown", "getList")


def test_get_method_spec_unknown_method(disco):
    with pytest.raises(KeyError, match="Method.*not found"):
        disco.get_method_spec("Clients", "nonExistent")


# ---------------------------------------------------------------------------
# resolve_http_method
# ---------------------------------------------------------------------------


def test_resolve_http_method(disco):
    assert disco.resolve_http_method("Clients", "getList") == "GET"
    assert disco.resolve_http_method("Clients", "create") == "POST"


def test_resolve_http_method_default(disco):
    assert disco.resolve_http_method("Unknown", "x") == "POST"
    assert disco.resolve_http_method("Unknown", "x", "GET") == "GET"


def test_resolve_http_method_missing_method(disco):
    assert disco.resolve_http_method("Clients", "nonExistent") == "POST"


def test_resolve_http_method_null_in_schema(disco):
    """Internal methods have http_method=None in schema, should use default."""
    assert disco.resolve_http_method("Clients", "validateCreation") == "POST"


# ---------------------------------------------------------------------------
# suggest_pagination_pair
# ---------------------------------------------------------------------------


def test_suggest_pagination_pair(disco):
    assert disco.suggest_pagination_pair("Clients", "getList") == "getListCount"


def test_suggest_pagination_pair_no_pair(disco):
    assert disco.suggest_pagination_pair("Clients", "create") is None


def test_suggest_pagination_pair_unknown_model(disco):
    assert disco.suggest_pagination_pair("Unknown") is None


def test_suggest_pagination_pair_no_pagination_key(disco):
    """Invoices model has no pagination key in test schema."""
    assert disco.suggest_pagination_pair("Invoices") is None


# ---------------------------------------------------------------------------
# generate_capabilities_report
# ---------------------------------------------------------------------------


def test_capabilities_report_markdown(disco):
    report = disco.generate_capabilities_report(format="markdown")
    assert "# Blesta API Capabilities Report" in report
    assert "## Clients" in report
    assert "## Invoices" in report
    assert "## cms.cms_pages (plugin)" in report
    assert "`getList`" in report
    assert "`create`" in report
    # Internal methods should not appear
    assert "validateCreation" not in report


def test_capabilities_report_json(disco):
    report = disco.generate_capabilities_report(format="json")
    data = json.loads(report)
    assert isinstance(data, list)
    model_names = [m["model"] for m in data]
    assert "Clients" in model_names
    assert "cms.cms_pages" in model_names


# ---------------------------------------------------------------------------
# generate_ai_index
# ---------------------------------------------------------------------------


def test_generate_ai_index(disco, tmp_path):
    out = tmp_path / "index.jsonl"
    count = disco.generate_ai_index(out)
    assert count > 0

    lines = out.read_text().strip().splitlines()
    assert len(lines) == count

    first = json.loads(lines[0])
    assert "model" in first
    assert "method" in first
    assert "http_method" in first
    assert "description" in first


def test_ai_index_excludes_internal(disco, tmp_path):
    out = tmp_path / "index.jsonl"
    disco.generate_ai_index(out)

    lines = out.read_text().strip().splitlines()
    for line in lines:
        entry = json.loads(line)
        assert entry["method"] != "validateCreation"


# ---------------------------------------------------------------------------
# Graceful fallback on missing schemas
# ---------------------------------------------------------------------------


def test_missing_core_schema(tmp_path):
    """Graceful fallback if core schema is missing."""
    plugin_path = tmp_path / "plugin.json"
    plugin_path.write_text(json.dumps(PLUGIN_SCHEMA))

    disco = BlestaDiscovery(
        core_schema_path=tmp_path / "nonexistent.json",
        plugin_schema_path=plugin_path,
    )
    models = disco.list_models()
    assert "cms.cms_pages" in models
    assert "Clients" not in models


def test_missing_both_schemas(tmp_path):
    """Graceful fallback if both schemas are missing."""
    disco = BlestaDiscovery(
        core_schema_path=tmp_path / "nope1.json",
        plugin_schema_path=tmp_path / "nope2.json",
    )
    assert disco.list_models() == []


def test_invalid_json_schema(tmp_path):
    """Graceful fallback if schema has invalid JSON."""
    bad = tmp_path / "bad.json"
    bad.write_text("{invalid json")

    disco = BlestaDiscovery(
        core_schema_path=bad,
        plugin_schema_path=tmp_path / "nope.json",
    )
    assert disco.list_models() == []


# ---------------------------------------------------------------------------
# Lazy loading
# ---------------------------------------------------------------------------


def test_lazy_loading(schema_dir):
    """Registry is not loaded until first access."""
    core_path, plugin_path = schema_dir
    disco = BlestaDiscovery(
        core_schema_path=core_path,
        plugin_schema_path=plugin_path,
    )
    assert disco._registry is None  # not loaded yet
    disco.list_models()
    assert disco._registry is not None  # loaded after first call


# ---------------------------------------------------------------------------
# Integration with bundled schemas
# ---------------------------------------------------------------------------


def test_default_schemas_load():
    """Default schemas (if present) load without error."""
    disco = BlestaDiscovery()
    models = disco.list_models()
    # If schemas exist, we should have models
    if _schema_files_exist():
        assert len(models) > 0
    else:
        assert models == []


def _schema_files_exist() -> bool:
    from blesta_sdk._discovery import _DEFAULT_CORE_SCHEMA

    return _DEFAULT_CORE_SCHEMA.exists()


def test_method_spec_is_frozen():
    """MethodSpec is a frozen dataclass."""
    spec = MethodSpec(
        model="X",
        method="y",
        http_method="GET",
        category="api",
        description="test",
    )
    with pytest.raises(AttributeError):
        spec.model = "Z"  # type: ignore[misc]
