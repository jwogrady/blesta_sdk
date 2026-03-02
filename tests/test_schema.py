"""Tests for the Blesta API schema and its parser.

Two groups:
1. Parser unit tests — mocked HTML fixtures, no network.
2. Schema validation tests — validate the committed JSON file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.extract_schema import parse_class_page, parse_model_list

SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent / "schemas" / "blesta_api_schema.json"
)


# ---------------------------------------------------------------------------
# HTML fixtures for parser unit tests
# ---------------------------------------------------------------------------

MINIMAL_MODEL_LIST_HTML = """
<html><body>
<div class="phpdocumentor-content">
  <ul>
    <li><a href="classes/Clients.html">Clients</a></li>
    <li><a href="classes/Invoices.html">Invoices</a></li>
    <li><a href="classes/Accounts.html">Accounts</a></li>
  </ul>
</div>
</body></html>
"""

SINGLE_METHOD_HTML = """
<html><body>
<article class="phpdocumentor-element -method -public">
  <h4 class="phpdocumentor-element__name" id="method_get">
    get()
  </h4>
  <p class="phpdocumentor-summary">Fetches a client</p>
  <code class="phpdocumentor-code phpdocumentor-signature">
    <span class="phpdocumentor-signature__visibility">public</span>
    <span class="phpdocumentor-signature__name">get</span>
    <span>(</span>
    <span class="phpdocumentor-signature__argument">
      <span class="phpdocumentor-signature__argument__return-type">int</span>
      <span class="phpdocumentor-signature__argument__name">$client_id</span>
    </span>
    <span>)</span>
    <span>:</span>
    <span class="phpdocumentor-signature__response_type">mixed</span>
  </code>
  <h5 class="phpdocumentor-argument-list__heading">Parameters</h5>
  <dl class="phpdocumentor-argument-list">
    <dt class="phpdocumentor-argument-list__entry">
      <span class="phpdocumentor-signature__argument__name">$client_id</span>
      :
      <span class="phpdocumentor-signature__argument__return-type">int</span>
    </dt>
    <dd class="phpdocumentor-argument-list__definition">
      <section class="phpdocumentor-description"><p>The client ID to fetch</p></section>
    </dd>
  </dl>
  <h5 class="phpdocumentor-return-value__heading">Return values</h5>
  <span class="phpdocumentor-signature__response_type">mixed</span>
  <section class="phpdocumentor-description">
    <p>A stdClass object representing the client</p>
  </section>
</article>
</body></html>
"""

OPTIONAL_PARAMS_HTML = """
<html><body>
<article class="phpdocumentor-element -method -public">
  <h4 class="phpdocumentor-element__name" id="method_getList">
    getList()
  </h4>
  <p class="phpdocumentor-summary">Fetches a list of all clients</p>
  <code class="phpdocumentor-code phpdocumentor-signature">
    <span class="phpdocumentor-signature__visibility">public</span>
    <span class="phpdocumentor-signature__name">getList</span>
    <span>(</span>
    <span class="phpdocumentor-signature__argument">
      <span>[</span>
      <span class="phpdocumentor-signature__argument__return-type">string</span>
      <span class="phpdocumentor-signature__argument__name">$status</span>
      <span>=</span>
      <span class="phpdocumentor-signature__argument__default-value">null</span>
      <span>]</span>
    </span>
    <span class="phpdocumentor-signature__argument">
      <span>[</span>
      <span>,</span>
      <span class="phpdocumentor-signature__argument__return-type">int</span>
      <span class="phpdocumentor-signature__argument__name">$page</span>
      <span>=</span>
      <span class="phpdocumentor-signature__argument__default-value">1</span>
      <span>]</span>
    </span>
    <span>)</span>
    <span>:</span>
    <span class="phpdocumentor-signature__response_type"
    >array&lt;string|int, mixed&gt;</span>
  </code>
  <h5 class="phpdocumentor-argument-list__heading">Parameters</h5>
  <dl class="phpdocumentor-argument-list">
    <dt class="phpdocumentor-argument-list__entry">
      <span class="phpdocumentor-signature__argument__name">$status</span>
      :
      <span class="phpdocumentor-signature__argument__return-type">string</span>
      =
      <span class="phpdocumentor-signature__argument__default-value">null</span>
    </dt>
    <dd class="phpdocumentor-argument-list__definition">
      <section class="phpdocumentor-description"><p>The status type</p></section>
    </dd>
    <dt class="phpdocumentor-argument-list__entry">
      <span class="phpdocumentor-signature__argument__name">$page</span>
      :
      <span class="phpdocumentor-signature__argument__return-type">int</span>
      =
      <span class="phpdocumentor-signature__argument__default-value">1</span>
    </dt>
    <dd class="phpdocumentor-argument-list__definition">
      <section class="phpdocumentor-description">
        <p>The page to return results for</p>
      </section>
    </dd>
  </dl>
  <h5 class="phpdocumentor-return-value__heading">Return values</h5>
  <span class="phpdocumentor-signature__response_type"
  >array&lt;string|int, mixed&gt;</span>
  <section class="phpdocumentor-description">
    <p>An array of stdClass objects</p>
  </section>
</article>
</body></html>
"""

NO_PARAMS_HTML = """
<html><body>
<article class="phpdocumentor-element -method -public">
  <h4 class="phpdocumentor-element__name" id="method_getCount">
    getCount()
  </h4>
  <p class="phpdocumentor-summary">Returns the total number</p>
  <code class="phpdocumentor-code phpdocumentor-signature">
    <span class="phpdocumentor-signature__visibility">public</span>
    <span class="phpdocumentor-signature__name">getCount</span>
    <span>(</span>
    <span>)</span>
    <span>:</span>
    <span class="phpdocumentor-signature__response_type">int</span>
  </code>
  <h5 class="phpdocumentor-return-value__heading">Return values</h5>
  <span class="phpdocumentor-signature__response_type">int</span>
  <section class="phpdocumentor-description"><p>The total count</p></section>
</article>
</body></html>
"""

CONSTRUCT_AND_METHOD_HTML = """
<html><body>
<article class="phpdocumentor-element -method -public">
  <h4 class="phpdocumentor-element__name" id="method___construct">
    __construct()
  </h4>
  <p class="phpdocumentor-summary">Initialize</p>
  <code class="phpdocumentor-code phpdocumentor-signature">
    <span class="phpdocumentor-signature__visibility">public</span>
    <span class="phpdocumentor-signature__name">__construct</span>
    <span>(</span><span>)</span>
  </code>
</article>
<article class="phpdocumentor-element -method -public">
  <h4 class="phpdocumentor-element__name" id="method_add">
    add()
  </h4>
  <p class="phpdocumentor-summary">Adds a record</p>
  <code class="phpdocumentor-code phpdocumentor-signature">
    <span class="phpdocumentor-signature__visibility">public</span>
    <span class="phpdocumentor-signature__name">add</span>
    <span>(</span>
    <span class="phpdocumentor-signature__argument">
      <span class="phpdocumentor-signature__argument__return-type"
      >array&lt;string|int, mixed&gt;</span>
      <span class="phpdocumentor-signature__argument__name">$vars</span>
    </span>
    <span>)</span>
    <span>:</span>
    <span class="phpdocumentor-signature__response_type">int</span>
  </code>
  <h5 class="phpdocumentor-argument-list__heading">Parameters</h5>
  <dl class="phpdocumentor-argument-list">
    <dt class="phpdocumentor-argument-list__entry">
      <span class="phpdocumentor-signature__argument__name">$vars</span>
      :
      <span class="phpdocumentor-signature__argument__return-type"
      >array&lt;string|int, mixed&gt;</span>
    </dt>
    <dd class="phpdocumentor-argument-list__definition">
      <section class="phpdocumentor-description"><p>The input vars</p></section>
    </dd>
  </dl>
</article>
</body></html>
"""

SUB_FIELDS_HTML = """
<html><body>
<article class="phpdocumentor-element -method -public">
  <h4 class="phpdocumentor-element__name" id="method_addAch">
    addAch()
  </h4>
  <p class="phpdocumentor-summary">Records an ACH account</p>
  <code class="phpdocumentor-code phpdocumentor-signature">
    <span class="phpdocumentor-signature__visibility">public</span>
    <span class="phpdocumentor-signature__name">addAch</span>
    <span>(</span>
    <span class="phpdocumentor-signature__argument">
      <span class="phpdocumentor-signature__argument__return-type"
      >array&lt;string|int, mixed&gt;</span>
      <span class="phpdocumentor-signature__argument__name">$vars</span>
    </span>
    <span>)</span>
    <span>:</span>
    <span class="phpdocumentor-signature__response_type">int</span>
  </code>
  <h5 class="phpdocumentor-argument-list__heading">Parameters</h5>
  <dl class="phpdocumentor-argument-list">
    <dt class="phpdocumentor-argument-list__entry">
      <span class="phpdocumentor-signature__argument__name">$vars</span>
      :
      <span class="phpdocumentor-signature__argument__return-type"
      >array&lt;string|int, mixed&gt;</span>
    </dt>
    <dd class="phpdocumentor-argument-list__definition">
      <section class="phpdocumentor-description">
        <p>An array of ACH account info including:</p>
        <ul>
          <li>contact_id The contact ID tied to this account</li>
          <li>first_name The first name on the account</li>
          <li>last_name The last name on the account</li>
        </ul>
      </section>
    </dd>
  </dl>
  <h5 class="phpdocumentor-return-value__heading">Return values</h5>
  <span class="phpdocumentor-signature__response_type">int</span>
  <section class="phpdocumentor-description">
    <p>The ACH account ID</p>
  </section>
</article>
</body></html>
"""

RETURN_SUB_FIELDS_HTML = """
<html><body>
<article class="phpdocumentor-element -method -public">
  <h4 class="phpdocumentor-element__name" id="method_getAch">
    getAch()
  </h4>
  <p class="phpdocumentor-summary">Fetches an ACH account</p>
  <code class="phpdocumentor-code phpdocumentor-signature">
    <span class="phpdocumentor-signature__visibility">public</span>
    <span class="phpdocumentor-signature__name">getAch</span>
    <span>(</span>
    <span class="phpdocumentor-signature__argument">
      <span class="phpdocumentor-signature__argument__return-type">int</span>
      <span class="phpdocumentor-signature__argument__name">$id</span>
    </span>
    <span>)</span>
    <span>:</span>
    <span class="phpdocumentor-signature__response_type">mixed</span>
  </code>
  <h5 class="phpdocumentor-argument-list__heading">Parameters</h5>
  <dl class="phpdocumentor-argument-list">
    <dt class="phpdocumentor-argument-list__entry">
      <span class="phpdocumentor-signature__argument__name">$id</span>
      :
      <span class="phpdocumentor-signature__argument__return-type">int</span>
    </dt>
    <dd class="phpdocumentor-argument-list__definition">
      <section class="phpdocumentor-description"><p>The account ID</p></section>
    </dd>
  </dl>
  <h5 class="phpdocumentor-return-value__heading">Return values</h5>
  <span class="phpdocumentor-signature__response_type">mixed</span>
  <section class="phpdocumentor-description">
    <p>An object containing:</p>
    <ul>
      <li>id The account ID</li>
      <li>routing The routing number</li>
    </ul>
  </section>
</article>
</body></html>
"""

CLASSIFICATION_HTML = """
<html><body>
<article class="phpdocumentor-element -method -public">
  <h4 class="phpdocumentor-element__name" id="method_get">get()</h4>
  <p class="phpdocumentor-summary">Fetches a record</p>
  <code class="phpdocumentor-code phpdocumentor-signature">
    <span class="phpdocumentor-signature__visibility">public</span>
    <span class="phpdocumentor-signature__name">get</span>
    <span>(</span><span>)</span>
    <span>:</span>
    <span class="phpdocumentor-signature__response_type">mixed</span>
  </code>
</article>
<article class="phpdocumentor-element -method -public">
  <h4 class="phpdocumentor-element__name" id="method_add">add()</h4>
  <p class="phpdocumentor-summary">Adds a record</p>
  <code class="phpdocumentor-code phpdocumentor-signature">
    <span class="phpdocumentor-signature__visibility">public</span>
    <span class="phpdocumentor-signature__name">add</span>
    <span>(</span><span>)</span>
    <span>:</span>
    <span class="phpdocumentor-signature__response_type">int</span>
  </code>
</article>
<article class="phpdocumentor-element -method -public">
  <h4 class="phpdocumentor-element__name" id="method_validateCreation">
    validateCreation()
  </h4>
  <p class="phpdocumentor-summary">Validates the creation</p>
  <code class="phpdocumentor-code phpdocumentor-signature">
    <span class="phpdocumentor-signature__visibility">public</span>
    <span class="phpdocumentor-signature__name">validateCreation</span>
    <span>(</span><span>)</span>
    <span>:</span>
    <span class="phpdocumentor-signature__response_type">bool</span>
  </code>
</article>
</body></html>
"""


# ---------------------------------------------------------------------------
# Parser unit tests
# ---------------------------------------------------------------------------


class TestParseModelList:
    def test_extracts_models(self):
        result = parse_model_list(MINIMAL_MODEL_LIST_HTML)
        assert len(result) == 3
        names = [m["name"] for m in result]
        assert names == ["Clients", "Invoices", "Accounts"]

    def test_urls_include_base(self):
        result = parse_model_list(MINIMAL_MODEL_LIST_HTML)
        for model in result:
            assert model["url"].startswith("https://source-docs.blesta.com/")
            assert model["url"].endswith(".html")

    def test_empty_html(self):
        result = parse_model_list("<html><body></body></html>")
        assert result == []


class TestParseClassPageBasic:
    def test_single_method(self):
        methods = parse_class_page(SINGLE_METHOD_HTML)
        assert "get" in methods
        m = methods["get"]
        assert m["description"] == "Fetches a client"
        assert m["return_type"] == "mixed"
        assert len(m["params"]) == 1

    def test_param_details(self):
        methods = parse_class_page(SINGLE_METHOD_HTML)
        param = methods["get"]["params"][0]
        assert param["name"] == "client_id"
        assert param["type"] == "int"
        assert param["required"] is True
        assert param["default"] is None
        assert param["description"] == "The client ID to fetch"

    def test_return_description(self):
        methods = parse_class_page(SINGLE_METHOD_HTML)
        assert "stdClass" in methods["get"]["return_description"]


class TestParseClassPageOptionalParams:
    def test_all_optional(self):
        methods = parse_class_page(OPTIONAL_PARAMS_HTML)
        m = methods["getList"]
        assert len(m["params"]) == 2
        for param in m["params"]:
            assert param["required"] is False

    def test_default_values(self):
        methods = parse_class_page(OPTIONAL_PARAMS_HTML)
        params = methods["getList"]["params"]
        assert params[0]["default"] == "null"
        assert params[1]["default"] == "1"

    def test_complex_return_type(self):
        methods = parse_class_page(OPTIONAL_PARAMS_HTML)
        assert methods["getList"]["return_type"] == "array<string|int, mixed>"


class TestParseClassPageNoParams:
    def test_no_params(self):
        methods = parse_class_page(NO_PARAMS_HTML)
        assert methods["getCount"]["params"] == []
        assert methods["getCount"]["return_type"] == "int"


class TestParseClassPageSkipsConstruct:
    def test_construct_filtered(self):
        methods = parse_class_page(CONSTRUCT_AND_METHOD_HTML)
        assert "__construct" not in methods
        assert "add" in methods

    def test_complex_types_preserved(self):
        methods = parse_class_page(CONSTRUCT_AND_METHOD_HTML)
        param = methods["add"]["params"][0]
        assert param["type"] == "array<string|int, mixed>"


class TestParseSubFields:
    def test_fields_extracted(self):
        methods = parse_class_page(SUB_FIELDS_HTML)
        param = methods["addAch"]["params"][0]
        assert "fields" in param
        assert len(param["fields"]) == 3
        assert param["fields"][0]["name"] == "contact_id"
        assert "contact ID" in param["fields"][0]["description"]

    def test_description_is_summary_only(self):
        methods = parse_class_page(SUB_FIELDS_HTML)
        param = methods["addAch"]["params"][0]
        assert param["description"] == "An array of ACH account info including:"
        assert "contact_id" not in param["description"]

    def test_no_fields_key_without_subfields(self):
        methods = parse_class_page(SINGLE_METHOD_HTML)
        param = methods["get"]["params"][0]
        assert "fields" not in param

    def test_return_sub_fields(self):
        methods = parse_class_page(RETURN_SUB_FIELDS_HTML)
        m = methods["getAch"]
        assert "return_fields" in m
        assert len(m["return_fields"]) == 2
        assert m["return_fields"][0]["name"] == "id"
        assert m["return_description"] == "An object containing:"

    def test_no_return_fields_without_subfields(self):
        methods = parse_class_page(SINGLE_METHOD_HTML)
        assert "return_fields" not in methods["get"]


class TestParseClassification:
    def test_api_method_has_http_method(self):
        methods = parse_class_page(CLASSIFICATION_HTML)
        assert methods["get"]["category"] == "api"
        assert methods["get"]["http_method"] == "GET"

    def test_add_method_is_post(self):
        methods = parse_class_page(CLASSIFICATION_HTML)
        assert methods["add"]["category"] == "api"
        assert methods["add"]["http_method"] == "POST"

    def test_internal_method_has_null_http_method(self):
        methods = parse_class_page(CLASSIFICATION_HTML)
        assert methods["validateCreation"]["category"] == "internal"
        assert methods["validateCreation"]["http_method"] is None


class TestParseSignatureReturnType:
    @pytest.mark.parametrize(
        "html_return_type,expected",
        [
            ("mixed", "mixed"),
            ("int", "int"),
            ("bool", "bool"),
            ("void", "void"),
            ("array&lt;string|int, mixed&gt;", "array<string|int, mixed>"),
            ("string|null", "string|null"),
        ],
    )
    def test_return_types(self, html_return_type, expected):
        html = f"""
        <html><body>
        <article class="phpdocumentor-element -method -public">
          <h4 class="phpdocumentor-element__name" id="method_test">test()</h4>
          <p class="phpdocumentor-summary">Test method</p>
          <code class="phpdocumentor-code phpdocumentor-signature">
            <span class="phpdocumentor-signature__visibility">public</span>
            <span class="phpdocumentor-signature__name">test</span>
            <span>(</span><span>)</span>
            <span>:</span>
            <span class="phpdocumentor-signature__response_type"
            >{html_return_type}</span>
          </code>
        </article>
        </body></html>
        """
        methods = parse_class_page(html)
        assert methods["test"]["return_type"] == expected


# ---------------------------------------------------------------------------
# Schema validation tests (validate the committed JSON)
# ---------------------------------------------------------------------------


class TestSchemaFile:
    @pytest.fixture(scope="class")
    def schema(self):
        assert SCHEMA_PATH.exists(), f"Schema file not found: {SCHEMA_PATH}"
        with open(SCHEMA_PATH) as f:
            return json.load(f)

    def test_schema_file_exists(self):
        assert SCHEMA_PATH.exists()

    def test_schema_is_valid_json(self):
        with open(SCHEMA_PATH) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_schema_has_metadata(self, schema):
        meta = schema["metadata"]
        assert "source_url" in meta
        assert "extracted_at" in meta
        assert "schema_version" in meta
        assert "model_count" in meta
        assert "total_methods" in meta
        assert meta["schema_version"] == "2.0.0"
        assert meta["source_type"] == "phpdocumentor_html"

    def test_schema_has_inference_metadata(self, schema):
        inference = schema["metadata"]["inference"]
        assert "http_method" in inference
        assert "category" in inference
        assert inference["http_method"]["source"] == "prefix_rules_v1"
        assert inference["category"]["source"] == "prefix_rules_v1"

    def test_schema_model_count(self, schema):
        assert schema["metadata"]["model_count"] >= 60

    def test_model_count_matches(self, schema):
        assert schema["metadata"]["model_count"] == len(schema["models"])

    def test_every_model_has_methods(self, schema):
        for name, model in schema["models"].items():
            assert "methods" in model, f"{name} missing 'methods'"
            assert len(model["methods"]) > 0, f"{name} has no methods"

    def test_method_structure(self, schema):
        for model_name in ["Clients", "Invoices", "Accounts"]:
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
            "Clients": ["get", "getList", "add", "edit", "delete"],
            "Invoices": ["get", "getList", "add", "edit"],
            "Accounts": ["getAch", "getCc", "getListAch", "getListCc"],
        }
        for model_name, methods in known.items():
            model = schema["models"][model_name]
            for method_name in methods:
                assert (
                    method_name in model["methods"]
                ), f"{model_name}.{method_name} not found"

    def test_schema_is_deterministic(self):
        with open(SCHEMA_PATH) as f:
            raw = f.read()
        data = json.loads(raw)
        reserialized = json.dumps(data, indent=2, sort_keys=True) + "\n"
        assert raw == reserialized, "Schema file is not deterministically sorted"

    def test_no_construct_methods(self, schema):
        for model_name, model in schema["models"].items():
            assert (
                "__construct" not in model["methods"]
            ), f"{model_name} contains __construct"

    def test_internal_methods_classified(self, schema):
        clients = schema["models"]["Clients"]
        if "validateCreation" in clients["methods"]:
            assert clients["methods"]["validateCreation"]["category"] == "internal"
            assert clients["methods"]["validateCreation"]["http_method"] is None

    def test_api_methods_have_http_method(self, schema):
        for model_name, model in schema["models"].items():
            for method_name, method in model["methods"].items():
                if method["category"] == "api" and method["http_method"] is not None:
                    assert method["http_method"] in (
                        "GET",
                        "POST",
                        "PUT",
                        "DELETE",
                    ), f"{model_name}.{method_name} has invalid http_method"

    def test_pagination_metadata(self, schema):
        # Clients should have getList/getListCount pair
        clients = schema["models"]["Clients"]
        assert "pagination" in clients
        assert "getList" in clients["pagination"]
        assert clients["pagination"]["getList"] == "getListCount"

    def test_fields_only_when_present(self, schema):
        for model_name, model in schema["models"].items():
            for method_name, method in model["methods"].items():
                for param in method["params"]:
                    if "fields" in param:
                        msg = f"{model_name}.{method_name}.{param['name']}"
                        assert len(param["fields"]) > 0, f"{msg} has empty fields"

    def test_sub_fields_extracted(self, schema):
        # Accounts.addAch should have sub-fields on its vars param
        accounts = schema["models"]["Accounts"]
        add_ach = accounts["methods"]["addAch"]
        vars_param = add_ach["params"][0]
        assert "fields" in vars_param, "Accounts.addAch.vars missing fields"
        field_names = [f["name"] for f in vars_param["fields"]]
        assert "contact_id" in field_names
        assert "first_name" in field_names
