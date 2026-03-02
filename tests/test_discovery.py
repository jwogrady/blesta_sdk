"""Tests for BlestaDiscovery — schema-driven API introspection."""

import json
import logging

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
    """Bundled schemas load via importlib.resources without error."""
    disco = BlestaDiscovery()
    models = disco.list_models()
    # Schemas are bundled inside the package, should always have models
    assert len(models) > 0


def test_bundled_schemas_via_importlib_resources():
    """Schemas are loadable via importlib.resources (pip-install path)."""
    from blesta_sdk._discovery import _bundled_schema_text

    text = _bundled_schema_text("blesta_api_schema.json")
    assert text is not None
    data = json.loads(text)
    assert "models" in data
    assert len(data["models"]) > 0

    plugin_text = _bundled_schema_text("blesta_plugin_schema.json")
    assert plugin_text is not None
    plugin_data = json.loads(plugin_text)
    assert "models" in plugin_data


def test_bundled_schema_missing_file():
    """_bundled_schema_text returns None for non-existent files."""
    from blesta_sdk._discovery import _bundled_schema_text

    assert _bundled_schema_text("nonexistent.json") is None


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


# ---------------------------------------------------------------------------
# _infer_http_method
# ---------------------------------------------------------------------------


class TestInferHttpMethod:
    """Tests for the prefix-based HTTP method heuristic."""

    def test_get_prefixes(self):
        from blesta_sdk._discovery import _infer_http_method

        assert _infer_http_method("getList") == "GET"
        assert _infer_http_method("get") == "GET"
        assert _infer_http_method("countAll") == "GET"
        assert _infer_http_method("searchClients") == "GET"

    def test_post_prefixes(self):
        from blesta_sdk._discovery import _infer_http_method

        assert _infer_http_method("create") == "POST"
        assert _infer_http_method("addPackage") == "POST"
        assert _infer_http_method("renewService") == "POST"
        assert _infer_http_method("processPayment") == "POST"
        assert _infer_http_method("sendNotification") == "POST"
        assert _infer_http_method("verifyEmail") == "POST"

    def test_put_prefixes(self):
        from blesta_sdk._discovery import _infer_http_method

        assert _infer_http_method("editClient") == "PUT"
        assert _infer_http_method("updateSettings") == "PUT"
        assert _infer_http_method("setStatus") == "PUT"

    def test_delete_prefixes(self):
        from blesta_sdk._discovery import _infer_http_method

        assert _infer_http_method("deleteInvoice") == "DELETE"
        assert _infer_http_method("removePackage") == "DELETE"
        assert _infer_http_method("unsetValue") == "DELETE"
        assert _infer_http_method("cancelService") == "DELETE"

    def test_ambiguous_returns_none(self):
        from blesta_sdk._discovery import _infer_http_method

        assert _infer_http_method("doSomething") is None
        assert _infer_http_method("validateCreation") is None
        assert _infer_http_method("run") is None

    def test_case_insensitive(self):
        from blesta_sdk._discovery import _infer_http_method

        assert _infer_http_method("GetList") == "GET"
        assert _infer_http_method("CREATE") == "POST"
        assert _infer_http_method("EDIT") == "PUT"
        assert _infer_http_method("DELETE") == "DELETE"


# ---------------------------------------------------------------------------
# _get_discovery module-level singleton (Fix A)
# ---------------------------------------------------------------------------


def test_get_discovery_singleton():
    """Module-level _get_discovery returns the same instance."""
    from blesta_sdk._discovery import _get_discovery

    _get_discovery.cache_clear()
    d1 = _get_discovery()
    d2 = _get_discovery()
    assert d1 is d2
    _get_discovery.cache_clear()


# ---------------------------------------------------------------------------
# OSError handling in _load_schema_file (Fix B)
# ---------------------------------------------------------------------------


def test_schema_path_is_directory(tmp_path):
    """Passing a directory as schema path degrades gracefully."""
    plugin_path = tmp_path / "plugin.json"
    plugin_path.write_text(json.dumps(PLUGIN_SCHEMA))

    disco = BlestaDiscovery(
        core_schema_path=tmp_path,  # a directory, not a file
        plugin_schema_path=plugin_path,
    )
    models = disco.list_models()
    assert "Clients" not in models
    assert "cms.cms_pages" in models


def test_schema_path_permission_error(tmp_path, monkeypatch):
    """Simulated PermissionError degrades gracefully."""
    import builtins

    real_open = builtins.open

    def mock_open(path, *args, **kwargs):
        if str(path) == str(tmp_path / "core.json"):
            raise PermissionError("denied")
        return real_open(path, *args, **kwargs)

    plugin_path = tmp_path / "plugin.json"
    plugin_path.write_text(json.dumps(PLUGIN_SCHEMA))
    # Create the file so it exists
    (tmp_path / "core.json").write_text(json.dumps(CORE_SCHEMA))

    monkeypatch.setattr(builtins, "open", mock_open)
    disco = BlestaDiscovery(
        core_schema_path=tmp_path / "core.json",
        plugin_schema_path=plugin_path,
    )
    models = disco.list_models()
    assert "Clients" not in models
    assert "cms.cms_pages" in models


# ---------------------------------------------------------------------------
# Model name collision warning (Fix C)
# ---------------------------------------------------------------------------


def test_model_collision_logs_warning(tmp_path, caplog):
    """Plugin model overwriting core model logs a warning."""
    # Plugin schema that duplicates a core model name
    colliding_plugin = {
        "metadata": {"schema_version": "2.0.0"},
        "models": {
            "Clients": {
                "methods": {
                    "getAll": {
                        "category": "api",
                        "description": "Plugin version",
                        "http_method": "GET",
                        "params": [],
                        "return_type": "array",
                        "return_description": "",
                        "signature": "",
                    }
                }
            }
        },
    }
    core_path = tmp_path / "core.json"
    plugin_path = tmp_path / "plugin.json"
    core_path.write_text(json.dumps(CORE_SCHEMA))
    plugin_path.write_text(json.dumps(colliding_plugin))

    with caplog.at_level(logging.WARNING, logger="blesta_sdk._discovery"):
        disco = BlestaDiscovery(
            core_schema_path=core_path,
            plugin_schema_path=plugin_path,
        )
        disco.list_models()

    assert any("Model collision detected: Clients" in m for m in caplog.messages)
    # The plugin version should have overwritten core
    methods = disco.list_methods("Clients")
    assert "getAll" in methods
    assert "getList" not in methods


# ---------------------------------------------------------------------------
# Schema structure validation (Fix D)
# ---------------------------------------------------------------------------


def test_models_not_dict(tmp_path, caplog):
    """Schema with 'models' as a list does not crash."""
    bad_schema = {"models": ["not", "a", "dict"]}
    core_path = tmp_path / "core.json"
    plugin_path = tmp_path / "plugin.json"
    core_path.write_text(json.dumps(bad_schema))
    plugin_path.write_text(json.dumps(PLUGIN_SCHEMA))

    with caplog.at_level(logging.WARNING, logger="blesta_sdk._discovery"):
        disco = BlestaDiscovery(
            core_schema_path=core_path,
            plugin_schema_path=plugin_path,
        )
        models = disco.list_models()

    assert "cms.cms_pages" in models
    assert any("'models' must be a dict" in m for m in caplog.messages)


def test_methods_not_dict(tmp_path, caplog):
    """Model with 'methods' as a list skips that model without crash."""
    bad_schema = {
        "models": {
            "Broken": {"methods": ["not", "a", "dict"]},
            "Invoices": CORE_SCHEMA["models"]["Invoices"],
        }
    }
    core_path = tmp_path / "core.json"
    plugin_path = tmp_path / "plugin.json"
    core_path.write_text(json.dumps(bad_schema))
    plugin_path.write_text(json.dumps(PLUGIN_SCHEMA))

    with caplog.at_level(logging.WARNING, logger="blesta_sdk._discovery"):
        disco = BlestaDiscovery(
            core_schema_path=core_path,
            plugin_schema_path=plugin_path,
        )
        models = disco.list_models()

    assert "Broken" not in models
    assert "Invoices" in models
    assert any("methods for Broken must be a dict" in m for m in caplog.messages)
