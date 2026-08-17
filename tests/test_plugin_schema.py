"""Tests for the Blesta plugin schema PHP parser.

Two groups:
1. Parser unit tests — mocked PHP fixtures, no network.
2. Schema validation tests — validate the committed JSON file.
3. I/O layer tests — mocked orchestration and CLI.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from tools.extract_plugin_schema import (
    _detect_pagination,
    build_plugin_schema,
    fetch_with_delay,
    parse_php_file,
)

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
        # "mixed" because two upstreams now contribute: the blesta/plugin-*
        # repos and the generated source docs. Per-model provenance is on each
        # model's "source_type".
        assert meta["source_type"] == "mixed"
        assert meta["source_types"] == [
            "github_php_docblocks",
            "phpdocumentor_html",
        ]
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


# ---------------------------------------------------------------------------
# I/O layer tests
# ---------------------------------------------------------------------------

PLUGIN_PHP_SOURCE = """\
<?php
class CmsPages extends AppModel
{
    /**
     * Get all CMS pages
     *
     * @return array A list of pages
     */
    public function getList() : array
    {
        return [];
    }

    /**
     * Get total page count
     *
     * @return int The count
     */
    public function getListCount() : int
    {
        return 0;
    }
}
"""


class TestPluginFetchWithDelay:
    def test_fetch_with_delay(self):
        mock_session = Mock()
        resp = Mock(text="<?php // code")
        resp.raise_for_status = Mock()
        mock_session.get.return_value = resp
        with patch("tools.extract_plugin_schema.time.sleep"):
            result = fetch_with_delay("http://x.com", mock_session, delay=0)
        assert result == "<?php // code"

    def test_fetch_with_delay_raises(self):
        mock_session = Mock()
        mock_session.get.side_effect = RuntimeError("network error")
        with pytest.raises(RuntimeError, match="network error"):
            fetch_with_delay("http://x.com", mock_session)


class TestPluginDetectPagination:
    def test_pagination_pair_found(self):
        methods = {"getList": {}, "getListCount": {}, "add": {}}
        assert _detect_pagination(methods) == {"getList": "getListCount"}

    def test_no_pagination(self):
        assert _detect_pagination({"add": {}, "edit": {}}) == {}


class TestBuildPluginSchema:
    def test_build_plugin_schema_success(self):
        def fetch_fn(url):
            return PLUGIN_PHP_SOURCE

        schema = build_plugin_schema(fetch_fn)
        assert "metadata" in schema
        assert "models" in schema
        assert schema["metadata"]["schema_version"] == "2.0.0"
        assert schema["metadata"]["model_count"] > 0
        assert schema["metadata"]["total_methods"] > 0

    def test_build_plugin_schema_fetch_failure(self):
        def fetch_fn(url):
            raise RuntimeError("fail")

        schema = build_plugin_schema(fetch_fn)
        assert schema["metadata"]["model_count"] == 0
        assert schema["models"] == {}

    def test_build_plugin_schema_empty_methods(self):
        def fetch_fn(url):
            return "<?php\nclass Foo {}\n"

        schema = build_plugin_schema(fetch_fn)
        assert schema["metadata"]["model_count"] == 0

    def test_build_plugin_schema_pagination_detected(self):
        def fetch_fn(url):
            return PLUGIN_PHP_SOURCE

        schema = build_plugin_schema(fetch_fn)
        for model_data in schema["models"].values():
            methods = model_data.get("methods", {})
            if "getList" in methods and "getListCount" in methods:
                assert "pagination" in model_data
                assert model_data["pagination"]["getList"] == "getListCount"


SOURCE_DOCS_CLASS_HTML = """
<html><body>
<article class="phpdocumentor-element -method -public">
  <h4 class="phpdocumentor-element__name" id="method_getList">getList()</h4>
  <p class="phpdocumentor-summary">Retrieve a list of tickets</p>
  <code class="phpdocumentor-code phpdocumentor-signature">
    <span class="phpdocumentor-signature__visibility">public</span>
    <span class="phpdocumentor-signature__name">getList</span>
    <span>(</span>
    <span class="phpdocumentor-signature__argument">
      <span>[</span>
      <span class="phpdocumentor-signature__argument__return-type">int</span>
      <span class="phpdocumentor-signature__argument__name">$client_id</span>
      <span>=</span>
      <span class="phpdocumentor-signature__argument__default-value">null</span>
      <span>]</span>
    </span>
    <span>)</span>
  </code>
  <h5 class="phpdocumentor-argument-list__heading">Parameters</h5>
  <dl class="phpdocumentor-argument-list">
    <dt class="phpdocumentor-argument-list__entry">
      <span class="phpdocumentor-signature__argument__name">$client_id</span>
      :
      <span class="phpdocumentor-signature__argument__return-type">int</span>
    </dt>
    <dd class="phpdocumentor-argument-list__definition">
      <section class="phpdocumentor-description"><p>The client ID</p></section>
    </dd>
  </dl>
</article>
<article class="phpdocumentor-element -method -public">
  <h4 class="phpdocumentor-element__name" id="method_getListCount">getListCount()</h4>
  <p class="phpdocumentor-summary">Retrieves the total number of tickets</p>
  <code class="phpdocumentor-code phpdocumentor-signature">
    <span class="phpdocumentor-signature__visibility">public</span>
    <span class="phpdocumentor-signature__name">getListCount</span>
    <span>(</span><span>)</span>
  </code>
</article>
</body></html>
"""


class TestBuildPluginSchemaFromSourceDocs:
    """Models with no public repo are read from the generated source docs.

    Support Manager ships inside the Blesta core distribution, so
    ``blesta/plugin-support_manager`` does not exist and PLUGIN_REGISTRY cannot
    reach it. The generated class docs carry the same docblocks.
    """

    @staticmethod
    def _fetch_fn(url):
        if url.startswith("https://source-docs.blesta.com/"):
            return SOURCE_DOCS_CLASS_HTML
        return PLUGIN_PHP_SOURCE

    def test_source_docs_models_registered(self):
        schema = build_plugin_schema(self._fetch_fn)
        model = schema["models"]["support_manager.support_manager_tickets"]
        assert set(model["methods"]) == {"getList", "getListCount"}
        assert (
            model["source"]
            == "https://source-docs.blesta.com/classes/SupportManagerTickets.html"
        )
        assert model["source_type"] == "phpdocumentor_html"
        assert model["pagination"]["getList"] == "getListCount"

    def test_metadata_reports_both_upstreams(self):
        schema = build_plugin_schema(self._fetch_fn)
        meta = schema["metadata"]
        assert meta["source_type"] == "mixed"
        assert meta["source_types"] == [
            "github_php_docblocks",
            "phpdocumentor_html",
        ]
        assert "support_manager" in meta["plugins"]
        assert meta["total_methods"] == sum(
            len(m["methods"]) for m in schema["models"].values()
        )

    def test_single_upstream_reports_its_own_source_type(self):
        # Not "mixed" when only one upstream answered — otherwise the field
        # would claim provenance the schema does not have.
        def php_only(url):
            if url.startswith("https://source-docs.blesta.com/"):
                raise RuntimeError("source docs unreachable")
            return PLUGIN_PHP_SOURCE

        schema = build_plugin_schema(php_only)
        assert schema["metadata"]["source_type"] == "github_php_docblocks"
        assert schema["metadata"]["source_types"] == ["github_php_docblocks"]
        assert not [k for k in schema["models"] if k.startswith("support_manager.")]

    def test_source_docs_model_with_no_methods_skipped(self):
        def empty_docs(url):
            if url.startswith("https://source-docs.blesta.com/"):
                return "<html><body>no methods here</body></html>"
            return PLUGIN_PHP_SOURCE

        schema = build_plugin_schema(empty_docs)
        assert not [k for k in schema["models"] if k.startswith("support_manager.")]
        assert "support_manager" not in schema["metadata"]["plugins"]


class TestPluginMainCLI:
    def test_main_dry_run(self, capsys):
        from tools.extract_plugin_schema import main

        mock_session = Mock()
        resp = Mock(text=PLUGIN_PHP_SOURCE)
        resp.raise_for_status = Mock()
        mock_session.get.return_value = resp
        mock_session.headers = {}

        with (
            patch("sys.argv", ["extract_plugin_schema", "--dry-run"]),
            patch("tools.extract_plugin_schema.time.sleep"),
            patch("requests.Session", return_value=mock_session),
        ):
            main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "metadata" in output
        assert "model_keys" in output

    def test_main_write_file(self, tmp_path):
        from tools.extract_plugin_schema import main

        output_file = tmp_path / "plugin.json"

        mock_session = Mock()
        resp = Mock(text=PLUGIN_PHP_SOURCE)
        resp.raise_for_status = Mock()
        mock_session.get.return_value = resp
        mock_session.headers = {}

        with (
            patch(
                "sys.argv",
                ["extract_plugin_schema", "--output", str(output_file)],
            ),
            patch("tools.extract_plugin_schema.time.sleep"),
            patch("requests.Session", return_value=mock_session),
        ):
            main()

        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert "metadata" in data
        assert "models" in data


class TestParsePhpEdgeCases:
    def test_method_without_docblock_skipped(self):
        source = """\
<?php
class Foo extends AppModel
{
    public function noDoc() : void {}
}
"""
        result = parse_php_file(source)
        assert result == {}

    def test_method_parse_exception_logged(self):
        source = """\
<?php
class Foo extends AppModel
{
    /**
     * Broken method
     */
    public function broken()
    {
    }
}
"""
        with patch(
            "tools.extract_plugin_schema._build_method_entry",
            side_effect=ValueError("parse error"),
        ):
            result = parse_php_file(source)
        assert result == {}

    def test_balanced_parens_no_close(self):
        from tools.extract_plugin_schema import _extract_balanced_parens

        # Handles missing close paren gracefully
        result = _extract_balanced_parens("(abc", 0)
        assert result == "abc"


# ---------------------------------------------------------------------------
# Support Manager coverage (issue #108)
# ---------------------------------------------------------------------------

# The copy BlestaDiscovery actually loads and the wheel actually ships, as
# distinct from the top-level schemas/ copy the tests above read. Asserting the
# new coverage against the top-level copy would prove nothing about what a
# consumer gets.
CANONICAL_PLUGIN_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "blesta_sdk"
    / "schemas"
    / "blesta_plugin_schema.json"
)

TICKETS_MODEL = "support_manager.support_manager_tickets"

SUPPORT_MANAGER_MODELS = (
    "support_manager.support_manager_departments",
    "support_manager.support_manager_kb_articles",
    "support_manager.support_manager_kb_categories",
    "support_manager.support_manager_responses",
    "support_manager.support_manager_settings",
    "support_manager.support_manager_staff",
    TICKETS_MODEL,
)


def _param(method: dict, name: str) -> dict | None:
    for param in method["params"]:
        if param["name"] == name:
            return param
    return None


def _field_names(param: dict) -> list[str]:
    return [f["name"] for f in param.get("fields", [])]


class TestSupportManagerCoverage:
    """Support Manager must be discoverable for ticket extraction.

    Support Manager ships inside the Blesta core distribution rather than as a
    ``blesta/plugin-*`` repository, so it is read from the generated class docs.
    Model keys are the API path segments: a request goes to
    ``/support_manager.support_manager_tickets/getList.json``.
    """

    @pytest.fixture(scope="class")
    def schema(self):
        assert (
            CANONICAL_PLUGIN_SCHEMA_PATH.exists()
        ), f"Schema file not found: {CANONICAL_PLUGIN_SCHEMA_PATH}"
        with open(CANONICAL_PLUGIN_SCHEMA_PATH) as f:
            return json.load(f)

    @pytest.mark.parametrize("model_key", SUPPORT_MANAGER_MODELS)
    def test_model_present(self, schema, model_key):
        assert model_key in schema["models"], f"{model_key} missing from plugin schema"
        assert schema["models"][model_key]["methods"], f"{model_key} has no methods"

    def test_plugin_listed_in_metadata(self, schema):
        assert "support_manager" in schema["metadata"]["plugins"]

    @pytest.mark.parametrize("model_key", SUPPORT_MANAGER_MODELS)
    def test_provenance_recorded(self, schema, model_key):
        model = schema["models"][model_key]
        assert model["source_type"] == "phpdocumentor_html"
        assert model["source"].startswith("https://source-docs.blesta.com/classes/")

    def test_github_sourced_models_also_record_provenance(self, schema):
        # The new key must be on every model, not only the new ones, or a
        # consumer cannot tell "read from the repos" from "key not written yet".
        for model_key, model in schema["models"].items():
            assert "source_type" in model, f"{model_key} has no source_type"
            if not model_key.startswith("support_manager."):
                assert model["source_type"] == "github_php_docblocks", model_key

    def test_ticket_read_surface(self, schema):
        methods = schema["models"][TICKETS_MODEL]["methods"]
        for name in ("get", "getList", "getListCount", "getTicketByCode"):
            assert name in methods, f"{TICKETS_MODEL}.{name} missing"
            assert methods[name]["http_method"] == "GET"
            assert methods[name]["category"] == "api"
            assert methods[name]["signature"]

    def test_ticket_client_filtering(self, schema):
        # The consumer requirement: tickets for one Blesta client.
        methods = schema["models"][TICKETS_MODEL]["methods"]
        for name in ("getList", "getListCount"):
            client_id = _param(methods[name], "client_id")
            assert client_id is not None, f"{name} has no client_id parameter"
            assert client_id["type"] == "int"
            assert client_id["required"] is False

    def test_ticket_pagination_pair(self, schema):
        pagination = schema["models"][TICKETS_MODEL]["pagination"]
        assert pagination["getList"] == "getListCount"

    def test_ticket_status_department_and_date_metadata(self, schema):
        methods = schema["models"][TICKETS_MODEL]["methods"]
        status = _param(methods["getList"], "status")
        assert status is not None and status["required"] is True
        filters = _param(methods["getList"], "filters")
        assert filters is not None
        for field in ("department_id", "priority", "last_reply", "assigned_staff"):
            assert field in _field_names(filters), f"filters lost {field}"
        # Enumerations a consumer needs to interpret the above.
        assert "getStatuses" in methods
        assert "getPriorities" in methods
        assert "getReplyTypes" in methods

    def test_ticket_history_is_reachable(self, schema):
        # Replies (and notes/logs) are the ticket history; they arrive through
        # get/getList rather than a separate replies model.
        for name in ("get", "getList"):
            method = schema["models"][TICKETS_MODEL]["methods"][name]
            assert _param(method, "get_replies") is not None
            assert _param(method, "reply_types") is not None
        assert "addReply" in schema["models"][TICKETS_MODEL]["methods"]

    def test_ticket_service_linkage_where_upstream_exposes_it(self, schema):
        methods = schema["models"][TICKETS_MODEL]["methods"]
        for name in ("add", "edit"):
            assert "service_id" in _field_names(_param(methods[name], "vars")), (
                f"{name} no longer documents the service_id var — "
                f"ticket/service linkage would become undiscoverable"
            )
        assert "validateClientService" in methods

    def test_documented_gaps_still_hold(self, schema):
        """Guards the gaps recorded in docs/support-manager-coverage.md.

        These assert an ABSENCE upstream, so they are the tests that should go
        red when Blesta starts documenting the surface — at which point the doc
        is wrong, not the schema. Do not delete them; update both together.
        """
        methods = schema["models"][TICKETS_MODEL]["methods"]
        filters = _field_names(_param(methods["getList"], "filters"))
        assert "service_id" not in filters, (
            "upstream now documents a service_id ticket filter — "
            "update docs/support-manager-coverage.md, it records this as a gap"
        )
        assert not [
            name
            for name, method in methods.items()
            if method["category"] == "api" and _param(method, "service_id") is not None
        ], (
            "upstream now exposes an API method taking service_id — "
            "update docs/support-manager-coverage.md"
        )
        # No documented field list on the ticket object itself, so a consumer
        # cannot learn from the docs which columns a ticket carries.
        assert "return_fields" not in methods["get"]
        assert "return_fields" not in methods["getList"]


class TestSchemaCopiesAgree:
    """The two copies of the plugin schema must not drift apart.

    ``schemas/`` is read by the tests above; ``src/blesta_sdk/schemas/`` is what
    the extractor writes, what ``BlestaDiscovery`` loads and what the wheel
    ships. They have already drifted in both directions once: the top-level copy
    carried an upstream ``unserialize`` -> ``safe_unserialize`` change that the
    shipped copy did not. Which one should survive is a judgement call for the
    maintainer; until it is made, at least make the divergence loud.
    """

    def test_plugin_schema_copies_match(self):
        if not PLUGIN_SCHEMA_PATH.exists():  # pragma: no cover
            pytest.skip("top-level schemas/ copy has been retired")
        with open(PLUGIN_SCHEMA_PATH) as f:
            top_level = json.load(f)
        with open(CANONICAL_PLUGIN_SCHEMA_PATH) as f:
            canonical = json.load(f)
        top_level["metadata"].pop("extracted_at", None)
        canonical["metadata"].pop("extracted_at", None)
        assert top_level == canonical, (
            "schemas/blesta_plugin_schema.json and "
            "src/blesta_sdk/schemas/blesta_plugin_schema.json have diverged. "
            "The extractor writes only the src/ copy; refresh the top-level one "
            "from it (indent=2, sort_keys, trailing newline) after re-extracting."
        )
