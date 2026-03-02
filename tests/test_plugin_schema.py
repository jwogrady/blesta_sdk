"""Tests for the Blesta plugin schema PHP parser.

Two groups:
1. Parser unit tests — mocked PHP fixtures, no network.
2. Schema validation tests — validate the committed JSON file.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tools.extract_plugin_schema import parse_php_file

PLUGIN_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent / "schemas" / "blesta_plugin_schema.json"
)


# ---------------------------------------------------------------------------
# PHP fixtures for parser unit tests
# ---------------------------------------------------------------------------

SIMPLE_METHOD_PHP = """\
<?php
class Example extends AppModel
{
    /**
     * Fetches a record by ID
     *
     * @param int $id The record ID
     * @return mixed The record object or false
     */
    public function get($id)
    {
        return $this->Record->select()->fetch();
    }
}
"""

OPTIONAL_PARAMS_PHP = """\
<?php
class Example extends AppModel
{
    /**
     * Returns a list of records
     *
     * @param int $company_id The company ID
     * @param int $page The page number
     * @param array $order Sort order
     * @return array An array of stdClass objects
     */
    public function getList(
        $company_id,
        $page = 1,
        array $order = ['date_updated' => 'desc']
    )
    {
        return [];
    }
}
"""

NO_PARAMS_PHP = """\
<?php
class Example extends AppModel
{
    /**
     * Returns the total count
     *
     * @return int The total number
     */
    public function getCount()
    {
        return 0;
    }
}
"""

MULTILINE_PARAM_PHP = """\
<?php
class Example extends AppModel
{
    /**
     * Adds a new record
     *
     * @param array $vars A list of input vars including:
     *
     *  - service_id The ID of the service
     *  - company_id The ID of the company
     *  - errors The errors encountered
     * @return stdClass The newly created object
     */
    public function add(array $vars)
    {
        return new stdClass();
    }
}
"""

MIXED_VISIBILITY_PHP = """\
<?php
class Example extends AppModel
{
    /**
     * Initialize
     */
    public function __construct()
    {
        parent::__construct();
    }

    /**
     * A public method
     *
     * @param int $id The ID
     * @return mixed The result
     */
    public function get($id)
    {
        return null;
    }

    /**
     * A private helper
     *
     * @param array $vars Input vars
     * @return array Validation rules
     */
    private function getRules(array $vars)
    {
        return [];
    }

    /**
     * A protected method
     *
     * @param string $event The event name
     */
    protected function triggerEvent($event)
    {
    }
}
"""

NO_DOCBLOCK_PHP = """\
<?php
class Example extends AppModel
{
    public function undocumented($id)
    {
        return null;
    }

    /**
     * A documented method
     *
     * @param int $id The record ID
     * @return mixed The record
     */
    public function get($id)
    {
        return null;
    }
}
"""

RETURN_TYPE_HINT_PHP = """\
<?php
class Example extends AppModel
{
    /**
     * Checks availability
     *
     * @param string $domain The domain name
     * @return bool True if available
     */
    public function checkAvailability($domain): bool
    {
        return true;
    }
}
"""

NULLABLE_TYPE_PHP = """\
<?php
class Example extends AppModel
{
    /**
     * Gets a record with optional company
     *
     * @param string $tld The TLD
     * @param int $company_id The company ID
     * @return mixed A TLD object or null
     */
    public function get($tld, $company_id = null)
    {
        return null;
    }
}
"""

MULTIPLE_METHODS_PHP = """\
<?php
class Example extends AppModel
{
    /**
     * Adds a record
     *
     * @param array $vars Input variables
     * @return int The new record ID
     */
    public function add(array $vars)
    {
        return 1;
    }

    /**
     * Edits a record
     *
     * @param int $id The record ID
     * @param array $vars Updated variables
     */
    public function edit($id, array $vars)
    {
    }

    /**
     * Deletes a record
     *
     * @param int $id The record ID
     */
    public function delete($id)
    {
    }
}
"""

NO_RETURN_DESC_PHP = """\
<?php
class Example extends AppModel
{
    /**
     * Removes a record
     *
     * @param int $id The record ID to remove
     */
    public function delete($id)
    {
    }
}
"""

SUB_FIELDS_PHP = """\
<?php
class Example extends AppModel
{
    /**
     * Adds a new TLD
     *
     * @param array $vars An array of input data including:
     *
     *  - tld The TLD to add
     *  - ns A numerically indexed array of nameservers
     *  - company_id The ID of the company (optional)
     * @return int The new TLD ID
     */
    public function add(array $vars)
    {
        return 1;
    }
}
"""

DASH_IN_DESCRIPTION_PHP = """\
<?php
class Example extends AppModel
{
    /**
     * Fetches a record - or null
     *
     * @param int $id The record ID
     * @return mixed The record or null
     */
    public function get($id)
    {
        return null;
    }
}
"""

CLASSIFICATION_PHP = """\
<?php
class Example extends AppModel
{
    /**
     * Gets a record
     *
     * @param int $id The ID
     * @return mixed The record
     */
    public function get($id)
    {
        return null;
    }

    /**
     * Adds a record
     *
     * @param array $vars Input variables
     * @return int The new ID
     */
    public function add(array $vars)
    {
        return 1;
    }

    /**
     * Validates input data
     *
     * @param array $vars Input variables
     * @return bool True if valid
     */
    public function validateData(array $vars)
    {
        return true;
    }
}
"""


# ---------------------------------------------------------------------------
# Parser unit tests
# ---------------------------------------------------------------------------


class TestParsePhpFileSimple:
    def test_single_method_extracted(self):
        methods = parse_php_file(SIMPLE_METHOD_PHP)
        assert "get" in methods

    def test_description(self):
        methods = parse_php_file(SIMPLE_METHOD_PHP)
        assert methods["get"]["description"] == "Fetches a record by ID"

    def test_return_type(self):
        methods = parse_php_file(SIMPLE_METHOD_PHP)
        assert methods["get"]["return_type"] == "mixed"

    def test_return_description(self):
        methods = parse_php_file(SIMPLE_METHOD_PHP)
        assert "record object" in methods["get"]["return_description"]

    def test_param_details(self):
        methods = parse_php_file(SIMPLE_METHOD_PHP)
        param = methods["get"]["params"][0]
        assert param["name"] == "id"
        assert param["type"] == "int"
        assert param["required"] is True
        assert param["default"] is None
        assert "record ID" in param["description"]

    def test_signature(self):
        methods = parse_php_file(SIMPLE_METHOD_PHP)
        sig = methods["get"]["signature"]
        assert sig.startswith("public get(")
        assert ": mixed" in sig


class TestParsePhpFileOptionalParams:
    def test_param_count(self):
        methods = parse_php_file(OPTIONAL_PARAMS_PHP)
        assert len(methods["getList"]["params"]) == 3

    def test_required_param(self):
        methods = parse_php_file(OPTIONAL_PARAMS_PHP)
        p = methods["getList"]["params"][0]
        assert p["name"] == "company_id"
        assert p["required"] is True
        assert p["default"] is None

    def test_optional_int_default(self):
        methods = parse_php_file(OPTIONAL_PARAMS_PHP)
        p = methods["getList"]["params"][1]
        assert p["name"] == "page"
        assert p["required"] is False
        assert p["default"] == "1"

    def test_optional_array_default(self):
        methods = parse_php_file(OPTIONAL_PARAMS_PHP)
        p = methods["getList"]["params"][2]
        assert p["name"] == "order"
        assert p["required"] is False
        assert p["default"] is not None
        assert "date_updated" in p["default"]

    def test_return_type(self):
        methods = parse_php_file(OPTIONAL_PARAMS_PHP)
        assert methods["getList"]["return_type"] == "array"


class TestParsePhpFileNoParams:
    def test_empty_params(self):
        methods = parse_php_file(NO_PARAMS_PHP)
        assert methods["getCount"]["params"] == []

    def test_return_type(self):
        methods = parse_php_file(NO_PARAMS_PHP)
        assert methods["getCount"]["return_type"] == "int"


class TestParsePhpFileMultilineParam:
    def test_sub_fields_extracted(self):
        methods = parse_php_file(MULTILINE_PARAM_PHP)
        param = methods["add"]["params"][0]
        assert "fields" in param
        field_names = [f["name"] for f in param["fields"]]
        assert "service_id" in field_names
        assert "company_id" in field_names

    def test_description_is_summary(self):
        methods = parse_php_file(MULTILINE_PARAM_PHP)
        param = methods["add"]["params"][0]
        assert "including" in param["description"]
        assert "service_id" not in param["description"]


class TestParsePhpFileVisibility:
    def test_skips_construct(self):
        methods = parse_php_file(MIXED_VISIBILITY_PHP)
        assert "__construct" not in methods

    def test_skips_private(self):
        methods = parse_php_file(MIXED_VISIBILITY_PHP)
        assert "getRules" not in methods

    def test_skips_protected(self):
        methods = parse_php_file(MIXED_VISIBILITY_PHP)
        assert "triggerEvent" not in methods

    def test_keeps_public(self):
        methods = parse_php_file(MIXED_VISIBILITY_PHP)
        assert "get" in methods


class TestParsePhpFileNoDocblock:
    def test_skips_undocumented(self):
        methods = parse_php_file(NO_DOCBLOCK_PHP)
        assert "undocumented" not in methods

    def test_keeps_documented(self):
        methods = parse_php_file(NO_DOCBLOCK_PHP)
        assert "get" in methods


class TestParsePhpFileReturnHint:
    def test_return_type_from_docblock(self):
        methods = parse_php_file(RETURN_TYPE_HINT_PHP)
        assert methods["checkAvailability"]["return_type"] == "bool"


class TestParsePhpFileNullable:
    def test_nullable_default(self):
        methods = parse_php_file(NULLABLE_TYPE_PHP)
        p = methods["get"]["params"][1]
        assert p["name"] == "company_id"
        assert p["required"] is False
        assert p["default"] == "null"


class TestParsePhpFileMultipleMethods:
    def test_all_methods_extracted(self):
        methods = parse_php_file(MULTIPLE_METHODS_PHP)
        assert set(methods.keys()) == {"add", "edit", "delete"}

    def test_method_structures(self):
        methods = parse_php_file(MULTIPLE_METHODS_PHP)
        for name, method in methods.items():
            assert "description" in method, f"{name} missing description"
            assert "signature" in method
            assert "params" in method
            assert "return_type" in method
            assert "return_description" in method
            assert isinstance(method["params"], list)


class TestParsePhpFileNoReturnDesc:
    def test_no_return_type(self):
        methods = parse_php_file(NO_RETURN_DESC_PHP)
        assert methods["delete"]["return_type"] == ""

    def test_empty_return_description(self):
        methods = parse_php_file(NO_RETURN_DESC_PHP)
        assert methods["delete"]["return_description"] == ""


class TestParsePhpFileSubFields:
    def test_fields_extracted(self):
        methods = parse_php_file(SUB_FIELDS_PHP)
        param = methods["add"]["params"][0]
        assert "fields" in param
        assert len(param["fields"]) == 3
        assert param["fields"][0]["name"] == "tld"
        assert "TLD to add" in param["fields"][0]["description"]

    def test_description_is_summary_only(self):
        methods = parse_php_file(SUB_FIELDS_PHP)
        param = methods["add"]["params"][0]
        assert (
            "tld" not in param["description"].lower()
            or "including" in param["description"].lower()
        )
        assert "- tld" not in param["description"]

    def test_no_fields_without_sub_field_markers(self):
        methods = parse_php_file(SIMPLE_METHOD_PHP)
        param = methods["get"]["params"][0]
        assert "fields" not in param

    def test_dash_in_description_not_treated_as_field(self):
        methods = parse_php_file(DASH_IN_DESCRIPTION_PHP)
        assert "get" in methods
        param = methods["get"]["params"][0]
        assert "fields" not in param


class TestParsePhpFileClassification:
    def test_api_get_method(self):
        methods = parse_php_file(CLASSIFICATION_PHP)
        assert methods["get"]["category"] == "api"
        assert methods["get"]["http_method"] == "GET"

    def test_api_add_method(self):
        methods = parse_php_file(CLASSIFICATION_PHP)
        assert methods["add"]["category"] == "api"
        assert methods["add"]["http_method"] == "POST"

    def test_internal_validate_method(self):
        methods = parse_php_file(CLASSIFICATION_PHP)
        assert methods["validateData"]["category"] == "internal"
        assert methods["validateData"]["http_method"] is None


# ---------------------------------------------------------------------------
# Schema validation tests (validate the committed JSON)
# ---------------------------------------------------------------------------


class TestPluginSchemaFile:
    @pytest.fixture(scope="class")
    def schema(self):
        assert (
            PLUGIN_SCHEMA_PATH.exists()
        ), f"Schema file not found: {PLUGIN_SCHEMA_PATH}"
        with open(PLUGIN_SCHEMA_PATH) as f:
            return json.load(f)

    def test_schema_file_exists(self):
        assert PLUGIN_SCHEMA_PATH.exists()

    def test_schema_is_valid_json(self):
        with open(PLUGIN_SCHEMA_PATH) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_schema_has_metadata(self, schema):
        meta = schema["metadata"]
        assert "source_type" in meta
        assert "extracted_at" in meta
        assert "schema_version" in meta
        assert "model_count" in meta
        assert "total_methods" in meta
        assert "plugins" in meta
        assert meta["source_type"] == "github_php_docblocks"
        assert meta["schema_version"] == "2.0.0"

    def test_schema_has_inference_metadata(self, schema):
        inference = schema["metadata"]["inference"]
        assert "http_method" in inference
        assert "category" in inference
        assert inference["http_method"]["source"] == "prefix_rules_v1"

    def test_plugin_model_count(self, schema):
        assert schema["metadata"]["model_count"] >= 8

    def test_model_count_matches(self, schema):
        assert schema["metadata"]["model_count"] == len(schema["models"])

    def test_every_model_has_methods(self, schema):
        for name, model in schema["models"].items():
            assert "methods" in model, f"{name} missing 'methods'"
            assert len(model["methods"]) > 0, f"{name} has no methods"

    def test_method_structure(self, schema):
        for model_name in [
            "domains.domains_domains",
            "webhooks.webhooks_webhooks",
        ]:
            assert model_name in schema["models"], f"{model_name} not in schema"
            model = schema["models"][model_name]
            for method_name, method in model["methods"].items():
                assert (
                    "description" in method
                ), f"{model_name}.{method_name} missing description"
                assert "signature" in method
                assert "params" in method
                assert "return_type" in method
                assert "category" in method
                assert "http_method" in method
                assert method["category"] in ("api", "internal")
                assert isinstance(method["params"], list)

    def test_known_methods_exist(self, schema):
        known = {
            "domains.domains_domains": [
                "getAll",
                "getList",
                "getListCount",
            ],
            "domains.domains_tlds": ["getList", "get", "add"],
            "cms.cms_pages": ["add", "edit"],
            "softaculous.softaculous_queued_services": [
                "add",
                "get",
                "delete",
            ],
            "webhooks.webhooks_webhooks": ["add", "edit"],
        }
        for model_name, method_names in known.items():
            model = schema["models"][model_name]
            for method_name in method_names:
                assert (
                    method_name in model["methods"]
                ), f"{model_name}.{method_name} not found"

    def test_schema_is_deterministic(self):
        with open(PLUGIN_SCHEMA_PATH) as f:
            raw = f.read()
        data = json.loads(raw)
        reserialized = json.dumps(data, indent=2, sort_keys=True) + "\n"
        assert raw == reserialized, "Schema file is not deterministically sorted"

    def test_no_construct_methods(self, schema):
        for model_name, model in schema["models"].items():
            assert (
                "__construct" not in model["methods"]
            ), f"{model_name} contains __construct"

    def test_model_keys_use_dot_notation(self, schema):
        for key in schema["models"]:
            assert re.match(
                r"\w+\.\w+", key
            ), f"Model key '{key}' does not use dot notation"

    def test_pagination_metadata(self, schema):
        # domains.domains_domains has getList/getListCount
        domains = schema["models"]["domains.domains_domains"]
        assert "pagination" in domains
        assert "getList" in domains["pagination"]
        assert domains["pagination"]["getList"] == "getListCount"

    def test_fields_only_when_present(self, schema):
        for model_name, model in schema["models"].items():
            for method_name, method in model["methods"].items():
                for param in method["params"]:
                    if "fields" in param:
                        msg = f"{model_name}.{method_name}.{param['name']}"
                        assert len(param["fields"]) > 0, f"{msg} has empty fields"
