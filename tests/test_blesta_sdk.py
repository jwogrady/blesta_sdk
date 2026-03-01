import json
import os
import sys
from unittest.mock import Mock, patch

import pytest
import requests
from requests.adapters import HTTPAdapter

import blesta_sdk
from blesta_sdk import BlestaRequest, BlestaResponse
from blesta_sdk._cli import cli
from blesta_sdk._dateutil import _month_boundaries

# _cli and _dateutil are internal modules. Tests below that use cli() and
# _month_boundaries() verify private behavior and may need updating if the
# internal module structure changes.


# --- Public API contract tests ---


def test_all_exports():
    """__all__ exposes exactly the public API surface."""
    assert set(blesta_sdk.__all__) == {
        "BlestaRequest",
        "BlestaResponse",
        "AsyncBlestaRequest",
        "__version__",
    }


def test_version():
    assert blesta_sdk.__version__ != "unknown"
    assert isinstance(blesta_sdk.__version__, str)


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


# --- BlestaRequest: auth_method ---


def test_header_auth_sets_headers():
    """auth_method='header' sets custom headers, no BasicAuth."""
    api = BlestaRequest(
        "https://example.com/api", "myuser", "mykey", auth_method="header"
    )
    assert api.auth_method == "header"
    assert api.session.auth is None
    assert api.session.headers["BLESTA-API-USER"] == "myuser"
    assert api.session.headers["BLESTA-API-KEY"] == "mykey"


def test_header_auth_default_is_basic():
    """Default auth_method is 'basic' (backward-compatible)."""
    api = BlestaRequest("https://example.com/api", "user", "key")
    assert api.auth_method == "basic"
    assert api.session.auth is not None


def test_header_auth_request_succeeds():
    """Header auth sends requests successfully."""
    api = BlestaRequest("https://example.com/api", "user", "key", auth_method="header")
    with patch.object(api.session, "get") as mock_get:
        mock_get.return_value = Mock(text='{"response": {}}', status_code=200)
        response = api.get("clients", "getList")
    assert response.status_code == 200
    mock_get.assert_called_once()


# --- BlestaRequest: context manager / close ---


def test_context_manager():
    api = BlestaRequest("https://example.com/api", "user", "key")
    with patch.object(api.session, "close") as mock_close:
        with api as ctx:
            assert ctx is api
            mock_close.assert_not_called()
        mock_close.assert_called_once()


def test_close():
    api = BlestaRequest("https://example.com/api", "user", "key")
    with patch.object(api.session, "close") as mock_close:
        api.close()
        mock_close.assert_called_once()


# --- BlestaResponse: data parsing ---


def test_data_returns_parsed_response_field():
    response = BlestaResponse('{"response": {"success": true}}', 200)
    assert response.data == {"success": True}


def test_data_returns_none_when_key_missing():
    response = BlestaResponse('{"other": "data"}', 200)
    assert response.data is None


def test_data_returns_none_for_csv():
    csv_text = '"id","name"\n"1","John"\n'
    response = BlestaResponse(csv_text, 200)
    assert response.data is None


# --- BlestaResponse: status_code ---


def test_blesta_response_status_code():
    response = BlestaResponse('{"response": {"id": 1}}', 200)
    assert response.status_code == 200


@pytest.mark.parametrize("code", [401, 404, 500])
def test_status_code_passthrough(blesta_request, code):
    with patch.object(blesta_request.session, "get") as mock_get:
        mock_get.return_value = Mock(
            text=json.dumps({"errors": {"message": "fail"}}),
            status_code=code,
        )
        response = blesta_request.get("clients", "getList")

    assert response.status_code == code
    assert response.errors() == {"message": "fail"}


# --- BlestaResponse: errors ---


def test_errors_returns_errors_dict():
    response = BlestaResponse('{"errors": {"message": "Error occurred"}}', 400)
    assert response.errors() == {"message": "Error occurred"}


def test_errors_returns_none_on_success():
    response = BlestaResponse('{"response": {"id": 1}}', 200)
    assert response.errors() is None


def test_errors_invalid_json():
    response = BlestaResponse("Invalid JSON", 200)
    assert response.errors() == {"error": "Invalid JSON response"}


def test_errors_fallback_non_200_without_errors_key():
    """Non-200 JSON body without 'errors' key returns fallback dict."""
    response = BlestaResponse('{"other": "data"}', 503)
    assert response.errors() == {"error": "HTTP 503 with no error details"}


# --- BlestaResponse: is_json / is_csv ---


def test_is_json_true():
    response = BlestaResponse('{"response": {"id": 1}}', 200)
    assert response.is_json is True
    assert response.is_csv is False


def test_is_csv_true():
    csv_text = '"id","name","amount"\n"1","John","100.00"\n"2","Jane","200.00"\n'
    response = BlestaResponse(csv_text, 200)
    assert response.is_csv is True
    assert response.is_json is False


def test_is_csv_false_for_empty():
    response = BlestaResponse("", 200)
    assert response.is_csv is False


def test_is_csv_false_for_single_line():
    response = BlestaResponse("just a string", 200)
    assert response.is_csv is False


# --- BlestaResponse: csv_data ---


def test_csv_data_parses_correctly():
    csv_text = '"id","name","amount"\n"1","John","100.00"\n"2","Jane","200.00"\n'
    response = BlestaResponse(csv_text, 200)
    data = response.csv_data
    assert len(data) == 2
    assert data[0] == {"id": "1", "name": "John", "amount": "100.00"}
    assert data[1] == {"id": "2", "name": "Jane", "amount": "200.00"}


def test_csv_data_returns_none_for_json():
    response = BlestaResponse('{"response": {"id": 1}}', 200)
    assert response.csv_data is None


def test_csv_data_cached_after_first_access():
    """Second csv_data access returns cached result, not a re-parse."""
    csv_text = '"id","name"\n"1","John"\n"2","Jane"\n'
    response = BlestaResponse(csv_text, 200)
    first = response.csv_data
    second = response.csv_data
    assert first is second  # same object, not re-parsed


def test_csv_data_caches_none_for_non_csv():
    """csv_data caches None result for non-CSV responses."""
    response = BlestaResponse('{"response": {"id": 1}}', 200)
    assert response.csv_data is None
    # Access again — should hit cache, not re-evaluate is_csv
    assert response.csv_data is None


def test_csv_response_no_errors():
    csv_text = '"id","name"\n"1","John"\n'
    response = BlestaResponse(csv_text, 200)
    assert response.errors() is None


def test_csv_response_with_error_status():
    csv_text = '"id","name"\n"1","John"\n'
    response = BlestaResponse(csv_text, 500)
    errors = response.errors()
    assert errors is not None
    assert "CSV response" in errors["error"]


# --- BlestaResponse: edge cases ---


def test_empty_body_response():
    response = BlestaResponse("", 200)
    assert response.is_json is False
    assert response.is_csv is False
    assert response.data is None
    assert response.errors() == {"error": "Invalid JSON response"}


def test_none_body_response():
    """None body should degrade gracefully, not raise TypeError."""
    response = BlestaResponse(None, 200)
    assert response.is_json is False
    assert response.is_csv is False
    assert response.data is None
    assert response.errors() == {"error": "Invalid JSON response"}


# --- Pagination tests ---


def test_iter_all_iterates(blesta_request):
    responses = [
        BlestaResponse(json.dumps({"response": [{"id": 1}, {"id": 2}]}), 200),
        BlestaResponse(json.dumps({"response": [{"id": 3}]}), 200),
        BlestaResponse(json.dumps({"response": []}), 200),
    ]

    with patch.object(blesta_request, "get", side_effect=responses):
        result = list(blesta_request.iter_all("invoices", "getList"))

    assert result == [{"id": 1}, {"id": 2}, {"id": 3}]


def test_get_all_returns_list(blesta_request):
    responses = [
        BlestaResponse(json.dumps({"response": [{"id": 1}]}), 200),
        BlestaResponse(json.dumps({"response": []}), 200),
    ]

    with patch.object(blesta_request, "get", side_effect=responses):
        result = blesta_request.get_all("invoices", "getList")

    assert isinstance(result, list)
    assert result == [{"id": 1}]


def test_iter_all_stops_on_error(blesta_request):
    responses = [
        BlestaResponse(json.dumps({"response": [{"id": 1}]}), 200),
        BlestaResponse('{"errors": {"message": "Forbidden"}}', 403),
    ]

    with patch.object(blesta_request, "get", side_effect=responses):
        result = list(blesta_request.iter_all("invoices", "getList"))

    assert result == [{"id": 1}]


def test_iter_all_stops_on_none_response(blesta_request):
    responses = [
        BlestaResponse('{"other": "data"}', 200),
    ]

    with patch.object(blesta_request, "get", side_effect=responses):
        result = list(blesta_request.iter_all("invoices", "getList"))

    assert result == []


def test_iter_all_stops_on_falsy_data(blesta_request):
    """iter_all treats falsy data (0, False) as end-of-pages."""
    responses = [
        BlestaResponse(json.dumps({"response": 0}), 200),
    ]

    with patch.object(blesta_request, "get", side_effect=responses):
        result = list(blesta_request.iter_all("invoices", "getList"))

    assert result == []


def test_iter_all_forwards_args(blesta_request):
    responses = [
        BlestaResponse(json.dumps({"response": []}), 200),
    ]

    with patch.object(blesta_request, "get", side_effect=responses) as mock_get:
        list(blesta_request.iter_all("invoices", "getList", {"status": "active"}))

    mock_get.assert_called_once_with(
        "invoices", "getList", {"status": "active", "page": 1}
    )


def test_iter_all_start_page(blesta_request):
    responses = [
        BlestaResponse(json.dumps({"response": []}), 200),
    ]

    with patch.object(blesta_request, "get", side_effect=responses) as mock_get:
        list(blesta_request.iter_all("invoices", "getList", start_page=5))

    mock_get.assert_called_once_with("invoices", "getList", {"page": 5})


def test_iter_all_single_object_response(blesta_request):
    responses = [
        BlestaResponse(json.dumps({"response": {"id": 1, "name": "John"}}), 200),
    ]

    with patch.object(blesta_request, "get", side_effect=responses):
        result = list(blesta_request.iter_all("clients", "get"))

    assert result == [{"id": 1, "name": "John"}]


# --- Report helper tests ---


def test_get_report_builds_correct_args(blesta_request):
    csv_text = '"id","amount"\n"1","100.00"\n'
    mock_response = BlestaResponse(csv_text, 200)

    with patch.object(blesta_request, "get", return_value=mock_response) as mock_get:
        response = blesta_request.get_report(
            "tax_liability", "2025-01-01", "2025-01-31"
        )

    mock_get.assert_called_once_with(
        "report_manager",
        "fetchAll",
        {
            "type": "tax_liability",
            "vars[start_date]": "2025-01-01",
            "vars[end_date]": "2025-01-31",
        },
    )
    assert response.is_csv
    assert len(response.csv_data) == 1


def test_get_report_with_extra_vars(blesta_request):
    csv_text = '"id","amount"\n"1","100.00"\n'
    mock_response = BlestaResponse(csv_text, 200)

    with patch.object(blesta_request, "get", return_value=mock_response) as mock_get:
        blesta_request.get_report(
            "tax_liability",
            "2025-01-01",
            "2025-01-31",
            extra_vars={"company_id": "1"},
        )

    expected_args = {
        "type": "tax_liability",
        "vars[start_date]": "2025-01-01",
        "vars[end_date]": "2025-01-31",
        "vars[company_id]": "1",
    }
    mock_get.assert_called_once_with("report_manager", "fetchAll", expected_args)


def test_get_report_extra_vars_already_wrapped(blesta_request):
    csv_text = '"id","amount"\n"1","100.00"\n'
    mock_response = BlestaResponse(csv_text, 200)

    with patch.object(blesta_request, "get", return_value=mock_response) as mock_get:
        blesta_request.get_report(
            "tax_liability",
            "2025-01-01",
            "2025-01-31",
            extra_vars={"vars[company_id]": "1"},
        )

    call_args = mock_get.call_args[0][2]
    assert "vars[company_id]" in call_args
    assert "vars[vars[company_id]]" not in call_args


# --- _month_boundaries tests (internal) ---


def test_month_boundaries_single_month():
    result = _month_boundaries("2025-01", "2025-01")
    assert result == [("2025-01-01", "2025-01-31", "2025-01")]


def test_month_boundaries_three_months():
    result = _month_boundaries("2025-01", "2025-03")
    assert len(result) == 3
    assert result[0] == ("2025-01-01", "2025-01-31", "2025-01")
    assert result[1] == ("2025-02-01", "2025-02-28", "2025-02")
    assert result[2] == ("2025-03-01", "2025-03-31", "2025-03")


def test_month_boundaries_february_leap_year():
    result = _month_boundaries("2024-02", "2024-02")
    assert result == [("2024-02-01", "2024-02-29", "2024-02")]


def test_month_boundaries_february_non_leap_year():
    result = _month_boundaries("2025-02", "2025-02")
    assert result == [("2025-02-01", "2025-02-28", "2025-02")]


def test_month_boundaries_crosses_year():
    result = _month_boundaries("2024-11", "2025-02")
    assert len(result) == 4
    assert result[0][2] == "2024-11"
    assert result[1][2] == "2024-12"
    assert result[2][2] == "2025-01"
    assert result[3][2] == "2025-02"


def test_month_boundaries_full_year():
    result = _month_boundaries("2025-01", "2025-12")
    assert len(result) == 12
    assert result[0][2] == "2025-01"
    assert result[11][2] == "2025-12"


def test_month_boundaries_reversed_raises():
    with pytest.raises(ValueError, match="after"):
        _month_boundaries("2025-06", "2025-01")


def test_month_boundaries_invalid_format_raises():
    with pytest.raises(ValueError):
        _month_boundaries("2025", "2025-01")


def test_month_boundaries_invalid_month_raises():
    with pytest.raises(ValueError):
        _month_boundaries("2025-13", "2025-14")


def test_month_boundaries_december_last_day():
    result = _month_boundaries("2025-12", "2025-12")
    assert result == [("2025-12-01", "2025-12-31", "2025-12")]


# --- get_report_series_pages tests ---


def _make_csv_response(csv_text, status_code=200):
    return BlestaResponse(csv_text, status_code)


def test_get_report_series_pages_yields_tuples(blesta_request):
    csv_text = '"Package","Revenue"\n"Hosting","100.00"\n'
    responses = [
        _make_csv_response(csv_text),
        _make_csv_response(csv_text),
        _make_csv_response(csv_text),
    ]

    with patch.object(blesta_request, "get_report", side_effect=responses):
        result = list(
            blesta_request.get_report_series_pages(
                "package_revenue", "2025-01", "2025-03"
            )
        )

    assert len(result) == 3
    assert all(isinstance(t, tuple) and len(t) == 2 for t in result)
    assert result[0][0] == "2025-01"
    assert result[1][0] == "2025-02"
    assert result[2][0] == "2025-03"


def test_get_report_series_pages_passes_extra_vars(blesta_request):
    csv_text = '"id","amount"\n"1","100.00"\n'

    with patch.object(
        blesta_request, "get_report", return_value=_make_csv_response(csv_text)
    ) as mock_report:
        list(
            blesta_request.get_report_series_pages(
                "tax_liability",
                "2025-01",
                "2025-01",
                extra_vars={"company_id": "1"},
            )
        )

    mock_report.assert_called_once_with(
        "tax_liability", "2025-01-01", "2025-01-31", {"company_id": "1"}
    )


def test_get_report_series_pages_yields_errors(blesta_request):
    csv_ok = _make_csv_response('"id","amount"\n"1","100"\n')
    csv_err = BlestaResponse('{"errors": {"message": "fail"}}', 500)

    with patch.object(
        blesta_request, "get_report", side_effect=[csv_ok, csv_err, csv_ok]
    ):
        result = list(
            blesta_request.get_report_series_pages(
                "package_revenue", "2025-01", "2025-03"
            )
        )

    assert len(result) == 3
    assert result[1][1].status_code == 500


def test_get_report_series_pages_invalid_range_raises(blesta_request):
    with pytest.raises(ValueError):
        list(
            blesta_request.get_report_series_pages(
                "package_revenue", "2025-06", "2025-01"
            )
        )


def test_get_report_series_pages_single_month(blesta_request):
    csv_text = '"id","amount"\n"1","100"\n'

    with patch.object(
        blesta_request, "get_report", return_value=_make_csv_response(csv_text)
    ):
        result = list(
            blesta_request.get_report_series_pages(
                "package_revenue", "2025-06", "2025-06"
            )
        )

    assert len(result) == 1
    assert result[0][0] == "2025-06"


def test_get_report_series_pages_calls_correct_dates(blesta_request):
    csv_text = '"id","amount"\n"1","100"\n'

    with patch.object(
        blesta_request, "get_report", return_value=_make_csv_response(csv_text)
    ) as mock_report:
        list(
            blesta_request.get_report_series_pages(
                "package_revenue", "2025-01", "2025-03"
            )
        )

    calls = mock_report.call_args_list
    assert calls[0].args[:3] == ("package_revenue", "2025-01-01", "2025-01-31")
    assert calls[1].args[:3] == ("package_revenue", "2025-02-01", "2025-02-28")
    assert calls[2].args[:3] == ("package_revenue", "2025-03-01", "2025-03-31")


# --- get_report_series tests ---


def test_get_report_series_returns_flat_list(blesta_request):
    csv1 = '"Package","Revenue"\n"Hosting","100"\n"SSL","50"\n'
    csv2 = '"Package","Revenue"\n"Hosting","110"\n"SSL","55"\n'

    with patch.object(
        blesta_request,
        "get_report",
        side_effect=[_make_csv_response(csv1), _make_csv_response(csv2)],
    ):
        result = blesta_request.get_report_series(
            "package_revenue", "2025-01", "2025-02"
        )

    assert len(result) == 4
    assert all(isinstance(r, dict) for r in result)


def test_get_report_series_adds_period_key(blesta_request):
    csv1 = '"Package","Revenue"\n"Hosting","100"\n'
    csv2 = '"Package","Revenue"\n"Hosting","110"\n'

    with patch.object(
        blesta_request,
        "get_report",
        side_effect=[_make_csv_response(csv1), _make_csv_response(csv2)],
    ):
        result = blesta_request.get_report_series(
            "package_revenue", "2025-01", "2025-02"
        )

    assert result[0]["_period"] == "2025-01"
    assert result[1]["_period"] == "2025-02"


def test_get_report_series_skips_http_errors(blesta_request):
    csv_ok = _make_csv_response('"Package","Revenue"\n"Hosting","100"\n')
    csv_err = BlestaResponse('{"errors": {"message": "fail"}}', 500)

    with patch.object(blesta_request, "get_report", side_effect=[csv_ok, csv_err]):
        result = blesta_request.get_report_series(
            "package_revenue", "2025-01", "2025-02"
        )

    assert len(result) == 1
    assert result[0]["_period"] == "2025-01"


def test_get_report_series_skips_non_csv(blesta_request):
    json_resp = BlestaResponse('{"response": {"id": 1}}', 200)
    csv_resp = _make_csv_response('"Package","Revenue"\n"Hosting","100"\n')

    with patch.object(blesta_request, "get_report", side_effect=[json_resp, csv_resp]):
        result = blesta_request.get_report_series(
            "package_revenue", "2025-01", "2025-02"
        )

    assert len(result) == 1
    assert result[0]["_period"] == "2025-02"


def test_get_report_series_empty_csv(blesta_request):
    csv_headers_only = _make_csv_response('"Package","Revenue"\n')

    with patch.object(blesta_request, "get_report", return_value=csv_headers_only):
        result = blesta_request.get_report_series(
            "package_revenue", "2025-01", "2025-01"
        )

    assert result == []


def test_get_report_series_all_errors_returns_empty(blesta_request):
    err = BlestaResponse('{"errors": {"message": "fail"}}', 500)

    with patch.object(blesta_request, "get_report", return_value=err):
        result = blesta_request.get_report_series(
            "package_revenue", "2025-01", "2025-03"
        )

    assert result == []


def test_get_report_series_passes_extra_vars(blesta_request):
    csv_text = '"id","amount"\n"1","100"\n'

    with patch.object(
        blesta_request, "get_report", return_value=_make_csv_response(csv_text)
    ) as mock_report:
        blesta_request.get_report_series(
            "tax_liability",
            "2025-01",
            "2025-01",
            extra_vars={"company_id": "1"},
        )

    mock_report.assert_called_once_with(
        "tax_liability", "2025-01-01", "2025-01-31", {"company_id": "1"}
    )


# --- to_dataframe tests ---


def test_to_dataframe_csv_response():
    csv_text = '"id","name","amount"\n"1","John","100.00"\n"2","Jane","200.00"\n'
    response = BlestaResponse(csv_text, 200)
    df = response.to_dataframe()
    assert len(df) == 2
    assert list(df.columns) == ["id", "name", "amount"]
    assert df.iloc[0]["name"] == "John"


def test_to_dataframe_json_list_response():
    json_text = json.dumps(
        {"response": [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]}
    )
    response = BlestaResponse(json_text, 200)
    df = response.to_dataframe()
    assert len(df) == 2
    assert "id" in df.columns


def test_to_dataframe_json_dict_response():
    json_text = json.dumps({"response": {"id": 1, "name": "John"}})
    response = BlestaResponse(json_text, 200)
    df = response.to_dataframe()
    assert len(df) == 1


def test_to_dataframe_no_pandas_raises():
    csv_text = '"id","name"\n"1","John"\n'
    response = BlestaResponse(csv_text, 200)
    with (
        patch.dict(sys.modules, {"pandas": None}),
        pytest.raises(ImportError, match="pip install pandas"),
    ):
        response.to_dataframe()


def test_to_dataframe_headers_only_csv():
    """Headers-only CSV (< 2 lines) is not recognized as CSV by is_csv."""
    response = BlestaResponse('"id","name"\n', 200)
    assert response.is_csv is False
    with pytest.raises(ValueError, match="neither CSV nor JSON"):
        response.to_dataframe()


def test_to_dataframe_non_parseable_raises():
    response = BlestaResponse("just some text", 200)
    with pytest.raises(ValueError, match="neither CSV nor JSON"):
        response.to_dataframe()


def test_to_dataframe_json_no_response_key_raises():
    json_text = json.dumps({"other": "data"})
    response = BlestaResponse(json_text, 200)
    with pytest.raises(ValueError, match="data is None"):
        response.to_dataframe()


def test_to_dataframe_string_data_raises():
    """JSON with non-dict/non-list data raises ValueError."""
    json_text = json.dumps({"response": "hello"})
    response = BlestaResponse(json_text, 200)
    with pytest.raises(ValueError, match="Cannot convert response of type str"):
        response.to_dataframe()


# --- CLI tests (internal) ---


def test_cli_missing_credentials(cli_env, capsys):
    with (
        patch.dict(
            os.environ,
            {"BLESTA_API_URL": "", "BLESTA_API_USER": "", "BLESTA_API_KEY": ""},
            clear=False,
        ),
        patch("sys.argv", ["blesta", "--model", "clients", "--method", "getList"]),
        pytest.raises(SystemExit, match="1"),
    ):
        cli()
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert "Missing API credentials" in output["error"]


def test_cli_successful_get(cli_env, capsys):
    mock_response = BlestaResponse('{"response": {"clients": []}}', 200)
    with (
        patch("sys.argv", ["blesta", "--model", "clients", "--method", "getList"]),
        patch("blesta_sdk._cli.BlestaRequest") as MockApi,
    ):
        MockApi.return_value.submit.return_value = mock_response
        cli()
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output == {"clients": []}


def test_cli_error_response(cli_env, capsys):
    mock_response = BlestaResponse('{"errors": {"message": "Not found"}}', 404)
    with (
        patch(
            "sys.argv",
            [
                "blesta",
                "--model",
                "clients",
                "--method",
                "get",
                "--params",
                "client_id=999",
            ],
        ),
        patch("blesta_sdk._cli.BlestaRequest") as MockApi,
        pytest.raises(SystemExit, match="1"),
    ):
        MockApi.return_value.submit.return_value = mock_response
        cli()
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output == {"message": "Not found"}


def test_cli_with_params_and_action(cli_env):
    mock_response = BlestaResponse('{"response": {"created": true}}', 200)
    with (
        patch(
            "sys.argv",
            [
                "blesta",
                "--model",
                "clients",
                "--method",
                "create",
                "--action",
                "POST",
                "--params",
                "name=John",
                "status=active",
            ],
        ),
        patch("blesta_sdk._cli.BlestaRequest") as MockApi,
    ):
        MockApi.return_value.submit.return_value = mock_response
        cli()

    MockApi.return_value.submit.assert_called_once_with(
        "clients", "create", {"name": "John", "status": "active"}, "POST"
    )


def test_cli_params_with_equals_in_value(cli_env):
    mock_response = BlestaResponse('{"response": {"ok": true}}', 200)
    with (
        patch(
            "sys.argv",
            [
                "blesta",
                "--model",
                "clients",
                "--method",
                "get",
                "--params",
                "filter=a=b",
            ],
        ),
        patch("blesta_sdk._cli.BlestaRequest") as MockApi,
    ):
        MockApi.return_value.submit.return_value = mock_response
        cli()

    MockApi.return_value.submit.assert_called_once_with(
        "clients", "get", {"filter": "a=b"}, "GET"
    )


def test_cli_last_request_flag(cli_env, capsys):
    mock_response = BlestaResponse('{"response": {"id": 1}}', 200)
    with (
        patch(
            "sys.argv",
            [
                "blesta",
                "--model",
                "clients",
                "--method",
                "get",
                "--params",
                "client_id=1",
                "--last-request",
            ],
        ),
        patch("blesta_sdk._cli.BlestaRequest") as MockApi,
    ):
        MockApi.return_value.submit.return_value = mock_response
        MockApi.return_value.get_last_request.return_value = {
            "url": "https://example.com/api/clients/get.json",
            "args": {"client_id": "1"},
        }
        cli()
    captured = capsys.readouterr()
    assert "Last Request URL:" in captured.out
    assert "Last Request Parameters:" in captured.out


def test_cli_last_request_flag_no_previous(cli_env, capsys):
    mock_response = BlestaResponse('{"response": {"id": 1}}', 200)
    with (
        patch(
            "sys.argv",
            ["blesta", "--model", "clients", "--method", "get", "--last-request"],
        ),
        patch("blesta_sdk._cli.BlestaRequest") as MockApi,
    ):
        MockApi.return_value.submit.return_value = mock_response
        MockApi.return_value.get_last_request.return_value = None
        cli()
    captured = capsys.readouterr()
    assert "No previous API request made." in captured.out


def test_cli_last_request_on_error(cli_env, capsys):
    """--last-request output is shown even on API errors."""
    mock_response = BlestaResponse('{"errors": {"message": "Not found"}}', 404)
    with (
        patch(
            "sys.argv",
            [
                "blesta",
                "--model",
                "clients",
                "--method",
                "get",
                "--params",
                "client_id=999",
                "--last-request",
            ],
        ),
        patch("blesta_sdk._cli.BlestaRequest") as MockApi,
        pytest.raises(SystemExit, match="1"),
    ):
        MockApi.return_value.submit.return_value = mock_response
        MockApi.return_value.get_last_request.return_value = {
            "url": "https://example.com/api/clients/get.json",
            "args": {"client_id": "999"},
        }
        cli()
    captured = capsys.readouterr()
    assert "Last Request URL:" in captured.out
    assert "Last Request Parameters:" in captured.out


# --- __repr__ tests ---


def test_blesta_request_repr():
    api = BlestaRequest("https://test.example.com/api", "myuser", "mykey")
    r = repr(api)
    assert r == "BlestaRequest(url='https://test.example.com/api/', user='myuser')"


def test_blesta_response_repr_short():
    resp = BlestaResponse('{"ok": true}', 200)
    r = repr(resp)
    assert "BlestaResponse(status_code=200" in r
    assert '{"ok": true}' in r
    assert "..." not in r


def test_blesta_response_repr_long():
    body = "x" * 100
    resp = BlestaResponse(body, 200)
    r = repr(resp)
    assert "..." in r
    assert "x" * 80 in r


def test_blesta_response_repr_none():
    resp = BlestaResponse(None, 0)
    r = repr(resp)
    assert "BlestaResponse(status_code=0" in r
    assert "None" in r


# --- Retry tests ---


def test_submit_no_retry_by_default(blesta_request):
    """Default max_retries=0 means no retry on failure."""
    with patch.object(blesta_request.session, "get") as mock_get:
        mock_get.side_effect = requests.ConnectionError("refused")
        response = blesta_request.get("clients", "getList")

    assert response.status_code == 0
    assert mock_get.call_count == 1


@patch("blesta_sdk._client.time.sleep")
def test_submit_retry_on_network_error(mock_sleep):
    api = BlestaRequest("https://test.example.com/api", "u", "k", max_retries=2)
    with patch.object(api.session, "get") as mock_get:
        mock_get.side_effect = [
            requests.ConnectionError("refused"),
            Mock(text='{"response": []}', status_code=200),
        ]
        response = api.get("clients", "getList")

    assert response.status_code == 200
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once_with(1)


@patch("blesta_sdk._client.time.sleep")
def test_submit_retry_on_500(mock_sleep):
    api = BlestaRequest("https://test.example.com/api", "u", "k", max_retries=2)
    with patch.object(api.session, "get") as mock_get:
        mock_get.side_effect = [
            Mock(text="Internal Server Error", status_code=500),
            Mock(text='{"response": []}', status_code=200),
        ]
        response = api.get("clients", "getList")

    assert response.status_code == 200
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once_with(1)


@patch("blesta_sdk._client.time.sleep")
def test_submit_no_retry_on_4xx(mock_sleep):
    api = BlestaRequest("https://test.example.com/api", "u", "k", max_retries=3)
    with patch.object(api.session, "get") as mock_get:
        mock_get.return_value = Mock(text='{"error": "not found"}', status_code=404)
        response = api.get("clients", "get")

    assert response.status_code == 404
    assert mock_get.call_count == 1
    mock_sleep.assert_not_called()


@patch("blesta_sdk._client.time.sleep")
def test_submit_retry_exhausted(mock_sleep):
    api = BlestaRequest("https://test.example.com/api", "u", "k", max_retries=2)
    with patch.object(api.session, "get") as mock_get:
        mock_get.side_effect = requests.ConnectionError("refused")
        response = api.get("clients", "getList")

    assert response.status_code == 0
    assert mock_get.call_count == 3  # initial + 2 retries
    assert mock_sleep.call_count == 2


@patch("blesta_sdk._client.time.sleep")
def test_submit_retry_backoff_timing(mock_sleep):
    api = BlestaRequest("https://test.example.com/api", "u", "k", max_retries=3)
    with patch.object(api.session, "post") as mock_post:
        mock_post.side_effect = requests.Timeout("timed out")
        api.post("clients", "create")

    # Backoff: 2^0=1, 2^1=2, 2^2=4
    assert mock_sleep.call_args_list == [
        ((1,),),
        ((2,),),
        ((4,),),
    ]


# --- Extract tests ---


def test_extract_multiple_targets(blesta_request):
    with patch.object(blesta_request, "get_all") as mock_get_all:
        mock_get_all.side_effect = [
            [{"id": 1}, {"id": 2}],
            [{"id": 10}],
        ]
        result = blesta_request.extract(
            [
                ("clients", "getList"),
                ("invoices", "getList"),
            ]
        )

    assert list(result.keys()) == ["clients.getList", "invoices.getList"]
    assert len(result["clients.getList"]) == 2
    assert len(result["invoices.getList"]) == 1


def test_extract_with_args(blesta_request):
    with patch.object(blesta_request, "get_all") as mock_get_all:
        mock_get_all.return_value = [{"id": 1}]
        result = blesta_request.extract(
            [
                ("clients", "getList", {"status": "active"}),
            ]
        )

    mock_get_all.assert_called_once_with("clients", "getList", {"status": "active"})
    assert "clients.getList" in result


def test_extract_empty_targets(blesta_request):
    result = blesta_request.extract([])
    assert result == {}


def test_extract_mixed_results(blesta_request):
    with patch.object(blesta_request, "get_all") as mock_get_all:
        mock_get_all.side_effect = [
            [{"id": 1}],
            [],
        ]
        result = blesta_request.extract(
            [
                ("clients", "getList"),
                ("packages", "getAll"),
            ]
        )

    assert len(result["clients.getList"]) == 1
    assert len(result["packages.getAll"]) == 0


# --- count() tests ---


def test_count_returns_int(blesta_request):
    """count() extracts integer from getListCount response."""
    response = BlestaResponse(json.dumps({"response": 22376}), 200)
    with patch.object(blesta_request, "get", return_value=response) as mock_get:
        result = blesta_request.count("transactions")
    assert result == 22376
    assert isinstance(result, int)
    mock_get.assert_called_once_with("transactions", "getListCount", None)


def test_count_custom_method(blesta_request):
    """count() respects custom method name."""
    response = BlestaResponse(json.dumps({"response": 5}), 200)
    with patch.object(blesta_request, "get", return_value=response) as mock_get:
        result = blesta_request.count("clients", "getStatusCount", {"status": "active"})
    mock_get.assert_called_once_with("clients", "getStatusCount", {"status": "active"})
    assert result == 5


def test_count_returns_zero_on_http_error(blesta_request):
    """count() returns 0 on non-200 status."""
    response = BlestaResponse('{"errors": {"message": "fail"}}', 500)
    with patch.object(blesta_request, "get", return_value=response):
        assert blesta_request.count("transactions") == 0


def test_count_returns_zero_on_none_data(blesta_request):
    """count() returns 0 when response has no 'response' key."""
    response = BlestaResponse('{"other": "data"}', 200)
    with patch.object(blesta_request, "get", return_value=response):
        assert blesta_request.count("transactions") == 0


def test_count_handles_string_number(blesta_request):
    """count() converts string '100' to int 100."""
    response = BlestaResponse(json.dumps({"response": "100"}), 200)
    with patch.object(blesta_request, "get", return_value=response):
        assert blesta_request.count("transactions") == 100


def test_count_returns_zero_for_non_numeric(blesta_request):
    """count() returns 0 for non-numeric response data."""
    response = BlestaResponse(json.dumps({"response": {"unexpected": "dict"}}), 200)
    with patch.object(blesta_request, "get", return_value=response):
        assert blesta_request.count("transactions") == 0


def test_count_returns_zero_for_zero(blesta_request):
    """count() returns 0 when API returns 0."""
    response = BlestaResponse(json.dumps({"response": 0}), 200)
    with patch.object(blesta_request, "get", return_value=response):
        assert blesta_request.count("transactions") == 0


# --- Integration test (requires valid .env credentials) ---


@pytest.mark.integration
def test_credentials(blesta_request):
    response = blesta_request.get("clients", "getList", {"status": "active"})
    assert isinstance(response, BlestaResponse)
    assert response.status_code == 200
    assert response.data is not None

    print(json.dumps(response.data, indent=4))


if __name__ == "__main__":
    pytest.main(["-v"])
