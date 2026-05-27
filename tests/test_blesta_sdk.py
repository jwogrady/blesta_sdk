import json
import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests
from requests.adapters import HTTPAdapter

import blesta_sdk
from blesta_sdk import BlestaDiscovery, BlestaRequest, BlestaResponse
from blesta_sdk._cli import cli
from blesta_sdk._dateutil import _month_boundaries

# _cli and _dateutil are internal modules. Tests below that use cli() and
# _month_boundaries() verify private behavior and may need updating if the
# internal module structure changes.


# --- Public API contract tests ---


def test_all_exports():
    """__all__ exposes exactly the public API surface."""
    assert set(blesta_sdk.__all__) == {
        "AsyncBlestaRequest",
        "BlestaAPIError",
        "BlestaAuthError",
        "BlestaConnectionError",
        "BlestaDiscovery",
        "BlestaEnvConfig",
        "BlestaError",
        "BlestaRateLimitError",
        "BlestaRequest",
        "BlestaResponse",
        "BlestaServerError",
        "MethodSpec",
        "PaginationError",
        "__version__",
    }


def test_version():
    assert blesta_sdk.__version__ != "unknown"
    assert isinstance(blesta_sdk.__version__, str)


def test_version_fallback_on_package_not_found():
    """_get_version returns 'unknown' when the package is not installed.

    Covers __init__.py lines 53-54.
    """
    from importlib.metadata import PackageNotFoundError

    with patch(
        "importlib.metadata.version", side_effect=PackageNotFoundError("blesta_sdk")
    ):
        import importlib

        importlib.reload(blesta_sdk)
        assert blesta_sdk.__version__ == "unknown"

    # Restore the real version for subsequent tests
    importlib.reload(blesta_sdk)


# --- BlestaRequest: HTTP method dispatch ---


@pytest.mark.parametrize(
    "method,session_method",
    [("get", "get"), ("post", "post"), ("put", "put"), ("delete", "delete")],
)
def test_http_method_returns_response(blesta_request, method, session_method):
    with patch.object(blesta_request.session, session_method) as mock:
        mock.return_value = Mock(text='{"success": true}', status_code=200)
        response = getattr(blesta_request, method)("clients", "action", {"k": "v"})

    assert isinstance(response, BlestaResponse)
    assert response.status_code == 200
    assert response.raw == '{"success": true}'


@pytest.mark.parametrize(
    "action,kwarg",
    [("GET", "params"), ("POST", "json"), ("PUT", "json"), ("DELETE", "json")],
)
def test_submit_passes_args_correctly(action, kwarg):
    """GET sends params=, POST/PUT/DELETE send json=."""
    api = BlestaRequest("https://example.com/api", "user", "key")
    with patch.object(api.session, action.lower()) as mock:
        mock.return_value = Mock(text='{"response": {}}', status_code=200)
        api.submit("clients", "getList", {"status": "active"}, action)

    _, call_kwargs = mock.call_args
    assert kwarg in call_kwargs
    assert call_kwargs[kwarg] == {"status": "active"}


def test_submit_invalid_action(blesta_request):
    # Intentional type violation: passing a string not in the Literal type
    # to verify the runtime ValueError guard.
    with pytest.raises(ValueError):
        blesta_request.submit("clients", "getList", {}, "INVALID")  # type: ignore[arg-type]


def test_request_exception(blesta_request):
    with patch.object(
        blesta_request.session, "get", side_effect=requests.RequestException("Error")
    ):
        response = blesta_request.get("clients", "getList")

    assert isinstance(response, BlestaResponse)
    assert response.status_code == 0
    assert "Error" in response.raw


# --- BlestaRequest: get_last_request ---


def test_get_last_request_returns_none_initially():
    api = BlestaRequest("https://example.com/api", "user", "key")
    assert api.get_last_request() is None


def test_get_last_request(blesta_request):
    with patch.object(blesta_request.session, "get") as mock_get:
        mock_get.return_value = Mock(text='{"success": true}', status_code=200)
        blesta_request.get("clients", "getList", {"status": "active"})

    last = blesta_request.get_last_request()
    assert last["url"] == blesta_request.base_url + "clients/getList.json"
    assert last["args"] == {"status": "active"}


# --- BlestaRequest: constructor ---


def test_base_url_normalization():
    a = BlestaRequest("https://x.com/api", "u", "k")
    b = BlestaRequest("https://x.com/api/", "u", "k")
    assert a.base_url == b.base_url == "https://x.com/api/"


def test_default_timeout():
    api = BlestaRequest("https://example.com/api", "user", "key")
    assert api.timeout == 30


def test_custom_timeout():
    api = BlestaRequest("https://example.com/api", "user", "key", timeout=60)
    assert api.timeout == 60


def test_timeout_passed_to_requests():
    api = BlestaRequest("https://example.com/api", "user", "key", timeout=10)
    with patch.object(api.session, "get") as mock_get:
        mock_get.return_value = Mock(text='{"response": {}}', status_code=200)
        api.get("clients", "getList")

    mock_get.assert_called_once_with(
        "https://example.com/api/clients/getList.json",
        params={},
        timeout=10,
    )


# --- BlestaRequest: connection pool tuning ---


def test_default_pool_settings():
    """Default pool_connections and pool_maxsize are 10."""
    api = BlestaRequest("https://example.com/api", "user", "key")
    adapter = api.session.get_adapter("https://example.com")
    assert adapter._pool_connections == 10
    assert adapter._pool_maxsize == 10


def test_custom_pool_settings():
    """Custom pool_connections and pool_maxsize are respected."""
    api = BlestaRequest(
        "https://example.com/api",
        "user",
        "key",
        pool_connections=5,
        pool_maxsize=20,
    )
    adapter = api.session.get_adapter("https://example.com")
    assert adapter._pool_connections == 5
    assert adapter._pool_maxsize == 20


def test_http_adapter_mounted():
    """Both http:// and https:// have the custom adapter."""
    api = BlestaRequest("https://example.com/api", "user", "key")
    https_adapter = api.session.get_adapter("https://example.com")
    http_adapter = api.session.get_adapter("http://example.com")
    assert isinstance(https_adapter, HTTPAdapter)
    assert isinstance(http_adapter, HTTPAdapter)
