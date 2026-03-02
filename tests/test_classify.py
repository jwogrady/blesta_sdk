"""Tests for Blesta method classification rules."""

from __future__ import annotations

import pytest

from tools._classify import (
    INFERENCE_SOURCE,
    classify_category,
    infer_http_method,
)

# ---------------------------------------------------------------------------
# classify_category tests
# ---------------------------------------------------------------------------


class TestClassifyCategory:
    @pytest.mark.parametrize(
        "method_name",
        [
            "validateCreation",
            "validateEmail",
            "validate",
            "formatNumber",
            "formatTerm",
            "buildEmail",
            "buildMessage",
            "isInstalled",
            "isLastInstance",
            "hasChildren",
            "hasPermission",
            "canSyncToParent",
        ],
    )
    def test_internal_by_prefix(self, method_name):
        assert classify_category(method_name) == "internal"

    @pytest.mark.parametrize(
        "method_name",
        [
            "creditCardType",
            "luhnValid",
            "hashPassword",
            "getDataPresenter",
            "getInstance",
            "getMethods",
            "getObservers",
            "getCacheMethods",
        ],
    )
    def test_internal_by_override(self, method_name):
        assert classify_category(method_name) == "internal"

    @pytest.mark.parametrize(
        "method_name",
        [
            "get",
            "getList",
            "add",
            "edit",
            "delete",
            "send",
            "search",
            "import",
            "process",
            "accept",
            "decline",
        ],
    )
    def test_api_methods(self, method_name):
        assert classify_category(method_name) == "api"

    def test_predicate_prefix_needs_word_boundary(self):
        # "import" starts with "i" but not "is" + uppercase
        assert classify_category("import") == "api"
        # "issue" starts with "is" but "s" is not uppercase
        assert classify_category("issue") == "api"
        # "cancel" starts with "can" but "c" is not uppercase
        assert classify_category("cancel") == "api"
        # "handle" starts with "ha" but not "has" + uppercase
        assert classify_category("handle") == "api"

    def test_exact_predicate_prefix_is_api(self):
        # Bare "is", "has", "can" without continuation are api
        assert classify_category("is") == "api"
        assert classify_category("has") == "api"
        assert classify_category("can") == "api"


# ---------------------------------------------------------------------------
# infer_http_method tests
# ---------------------------------------------------------------------------


class TestInferHttpMethod:
    @pytest.mark.parametrize(
        "method_name",
        ["get", "getList", "getAll", "getListCount", "getByAlias"],
    )
    def test_get_methods(self, method_name):
        assert infer_http_method(method_name) == "GET"

    @pytest.mark.parametrize(
        "method_name",
        ["count", "countByStatus", "search", "searchContactLogs", "fetchAll"],
    )
    def test_get_other_prefixes(self, method_name):
        assert infer_http_method(method_name) == "GET"

    @pytest.mark.parametrize(
        "method_name",
        ["add", "addAch", "create", "createFromServices", "send", "sendCustom"],
    )
    def test_post_methods(self, method_name):
        assert infer_http_method(method_name) == "POST"

    @pytest.mark.parametrize(
        "method_name",
        ["edit", "editAch", "update", "updateStatus", "setMeta", "enable", "disable"],
    )
    def test_put_methods(self, method_name):
        assert infer_http_method(method_name) == "PUT"

    @pytest.mark.parametrize(
        "method_name",
        ["delete", "deleteAch", "remove", "removeByPlugin", "clearCache", "unsetMeta"],
    )
    def test_delete_methods(self, method_name):
        assert infer_http_method(method_name) == "DELETE"

    @pytest.mark.parametrize(
        "method_name",
        ["accept", "decline", "auth", "errors", "baseUri", "delivered"],
    )
    def test_ambiguous_api_methods_return_none(self, method_name):
        assert classify_category(method_name) == "api"
        assert infer_http_method(method_name) is None

    @pytest.mark.parametrize(
        "method_name",
        ["validateCreation", "formatNumber", "buildEmail", "isInstalled"],
    )
    def test_internal_methods_return_none(self, method_name):
        assert infer_http_method(method_name) is None


class TestInferenceSource:
    def test_source_is_string(self):
        assert isinstance(INFERENCE_SOURCE, str)
        assert INFERENCE_SOURCE == "prefix_rules_v1"
