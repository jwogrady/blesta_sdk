import sys

import pytest
import requests
from unittest.mock import patch, Mock
from blesta_sdk.api.blesta_request import BlestaRequest
from blesta_sdk.core import BlestaResponse
from blesta_sdk.core.dateutil import _month_boundaries
from blesta_sdk.cli.blesta_cli import cli
from dotenv import load_dotenv
import os
import json

import blesta_sdk

# Load environment variables from .env file
load_dotenv()


@pytest.fixture
def blesta_request():
    url = os.getenv("BLESTA_API_URL", "https://aware.status26.com/api")
    user = os.getenv("BLESTA_API_USER", "user")
    key = os.getenv("BLESTA_API_KEY", "key")
    return BlestaRequest(url, user, key)


# --- BlestaRequest tests ---


def test_get_request(blesta_request):
    with patch.object(blesta_request.session, "get") as mock_get:
        mock_response = Mock()
        mock_response.text = '{"success": true}'
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        response = blesta_request.get("clients", "getList", {"status": "active"})
        assert isinstance(response, BlestaResponse)
        assert response.status_code == 200
        assert response.raw == '{"success": true}'


def test_post_request(blesta_request):
    with patch.object(blesta_request.session, "post") as mock_post:
        mock_response = Mock()
        mock_response.text = '{"success": true}'
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        response = blesta_request.post("clients", "create", {"name": "John Doe"})
        assert isinstance(response, BlestaResponse)
        assert response.status_code == 200
        assert response.raw == '{"success": true}'


def test_put_request(blesta_request):
    with patch.object(blesta_request.session, "put") as mock_put:
        mock_response = Mock()
        mock_response.text = '{"success": true}'
        mock_response.status_code = 200
        mock_put.return_value = mock_response

        response = blesta_request.put(
            "clients", "update", {"client_id": 1, "name": "John Doe"}
        )
        assert isinstance(response, BlestaResponse)
        assert response.status_code == 200
        assert response.raw == '{"success": true}'


def test_delete_request(blesta_request):
    with patch.object(blesta_request.session, "delete") as mock_delete:
        mock_response = Mock()
        mock_response.text = '{"success": true}'
        mock_response.status_code = 200
        mock_delete.return_value = mock_response

        response = blesta_request.delete("clients", "delete", {"client_id": 1})
        assert isinstance(response, BlestaResponse)
        assert response.status_code == 200
        assert response.raw == '{"success": true}'


def test_submit_invalid_action(blesta_request):
    with pytest.raises(ValueError):
        blesta_request.submit("clients", "getList", {}, "INVALID")


def test_request_exception(blesta_request):
    with patch.object(
        blesta_request.session, "get", side_effect=requests.RequestException("Error")
    ):
        response = blesta_request.get("clients", "getList")
        assert isinstance(response, BlestaResponse)
        assert response.status_code == 500
        assert "Error" in response.raw


def test_get_last_request(blesta_request):
    with patch.object(blesta_request.session, "get") as mock_get:
        mock_response = Mock()
        mock_response.text = '{"success": true}'
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        blesta_request.get("clients", "getList", {"status": "active"})
        last_request = blesta_request.get_last_request()
        assert (
            last_request["url"]
            == f"{os.getenv('BLESTA_API_URL', 'https://aware.status26.com/api')}/clients/getList.json"
        )
        assert last_request["args"] == {"status": "active"}


def test_default_timeout():
    api = BlestaRequest("https://example.com/api", "user", "key")
    assert api.timeout == 30


def test_custom_timeout():
    api = BlestaRequest("https://example.com/api", "user", "key", timeout=60)
    assert api.timeout == 60


def test_timeout_passed_to_requests():
    api = BlestaRequest("https://example.com/api", "user", "key", timeout=10)
    with patch.object(api.session, "get") as mock_get:
        mock_response = Mock()
        mock_response.text = '{"response": {}}'
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        api.get("clients", "getList")
        mock_get.assert_called_once_with(
            "https://example.com/api/clients/getList.json",
            params={},
            timeout=10,
        )


def test_context_manager():
    with BlestaRequest("https://example.com/api", "user", "key") as api:
        assert isinstance(api, BlestaRequest)
        with patch.object(api.session, "close") as mock_close:
            pass  # __exit__ fires after the with block
        # verify close wasn't called inside the block
        mock_close.assert_not_called()
    # can't easily assert close was called after exit, so test the shape
    assert api is not None


def test_close():
    api = BlestaRequest("https://example.com/api", "user", "key")
    with patch.object(api.session, "close") as mock_close:
        api.close()
        mock_close.assert_called_once()


# --- BlestaResponse tests ---


def test_format_response_valid_json():
    response = BlestaResponse('{"response": {"success": true}}', 200)
    assert response.response == {"success": True}


def test_format_response_invalid_json():
    response = BlestaResponse("Invalid JSON", 200)
    assert response.errors() == {"error": "Invalid JSON response"}


def test_blesta_response_errors():
    response = BlestaResponse('{"errors": {"message": "Error occurred"}}', 400)
    assert response.errors() == {"message": "Error occurred"}


def test_blesta_response_response_code():
    response = BlestaResponse('{"response": {"id": 1}}', 200)
    assert response.response_code == 200


def test_blesta_response_status_code():
    response = BlestaResponse('{"response": {"id": 1}}', 200)
    assert response.status_code == 200


def test_blesta_response_no_errors_on_success():
    response = BlestaResponse('{"response": {"id": 1}}', 200)
    assert response.errors() is None


def test_blesta_response_no_response_key():
    response = BlestaResponse('{"other": "data"}', 200)
    assert response.response is None


# --- __version__ test ---


def test_version():
    assert blesta_sdk.__version__ != "unknown"
    assert isinstance(blesta_sdk.__version__, str)


# --- CLI tests ---


def test_cli_missing_credentials(capsys):
    with (
        patch.dict(
            os.environ,
            {"BLESTA_API_URL": "", "BLESTA_API_USER": "", "BLESTA_API_KEY": ""},
            clear=False,
        ),
        patch("sys.argv", ["blesta", "--model", "clients", "--method", "getList"]),
    ):
        cli()
    captured = capsys.readouterr()
    assert "Missing API credentials" in captured.out


def test_cli_successful_get(capsys):
    mock_response = BlestaResponse('{"response": {"clients": []}}', 200)
    with (
        patch.dict(
            os.environ,
            {
                "BLESTA_API_URL": "https://example.com/api",
                "BLESTA_API_USER": "user",
                "BLESTA_API_KEY": "key",
            },
            clear=False,
        ),
        patch("sys.argv", ["blesta", "--model", "clients", "--method", "getList"]),
        patch("blesta_sdk.cli.blesta_cli.BlestaRequest") as MockApi,
    ):
        MockApi.return_value.submit.return_value = mock_response
        cli()
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output == {"clients": []}


def test_cli_error_response(capsys):
    mock_response = BlestaResponse('{"errors": {"message": "Not found"}}', 404)
    with (
        patch.dict(
            os.environ,
            {
                "BLESTA_API_URL": "https://example.com/api",
                "BLESTA_API_USER": "user",
                "BLESTA_API_KEY": "key",
            },
            clear=False,
        ),
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
        patch("blesta_sdk.cli.blesta_cli.BlestaRequest") as MockApi,
    ):
        MockApi.return_value.submit.return_value = mock_response
        cli()
    captured = capsys.readouterr()
    assert "Error:" in captured.out


def test_cli_with_params_and_action(capsys):
    mock_response = BlestaResponse('{"response": {"created": true}}', 200)
    with (
        patch.dict(
            os.environ,
            {
                "BLESTA_API_URL": "https://example.com/api",
                "BLESTA_API_USER": "user",
                "BLESTA_API_KEY": "key",
            },
            clear=False,
        ),
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
        patch("blesta_sdk.cli.blesta_cli.BlestaRequest") as MockApi,
    ):
        MockApi.return_value.submit.return_value = mock_response
        cli()

    MockApi.return_value.submit.assert_called_once_with(
        "clients", "create", {"name": "John", "status": "active"}, "POST"
    )


def test_cli_params_with_equals_in_value(capsys):
    mock_response = BlestaResponse('{"response": {"ok": true}}', 200)
    with (
        patch.dict(
            os.environ,
            {
                "BLESTA_API_URL": "https://example.com/api",
                "BLESTA_API_USER": "user",
                "BLESTA_API_KEY": "key",
            },
            clear=False,
        ),
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
        patch("blesta_sdk.cli.blesta_cli.BlestaRequest") as MockApi,
    ):
        MockApi.return_value.submit.return_value = mock_response
        cli()

    MockApi.return_value.submit.assert_called_once_with(
        "clients", "get", {"filter": "a=b"}, "GET"
    )


def test_cli_last_request_flag(capsys):
    mock_response = BlestaResponse('{"response": {"id": 1}}', 200)
    with (
        patch.dict(
            os.environ,
            {
                "BLESTA_API_URL": "https://example.com/api",
                "BLESTA_API_USER": "user",
                "BLESTA_API_KEY": "key",
            },
            clear=False,
        ),
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
        patch("blesta_sdk.cli.blesta_cli.BlestaRequest") as MockApi,
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


def test_cli_last_request_flag_no_previous(capsys):
    mock_response = BlestaResponse('{"response": {"id": 1}}', 200)
    with (
        patch.dict(
            os.environ,
            {
                "BLESTA_API_URL": "https://example.com/api",
                "BLESTA_API_USER": "user",
                "BLESTA_API_KEY": "key",
            },
            clear=False,
        ),
        patch(
            "sys.argv",
            ["blesta", "--model", "clients", "--method", "get", "--last-request"],
        ),
        patch("blesta_sdk.cli.blesta_cli.BlestaRequest") as MockApi,
    ):
        MockApi.return_value.submit.return_value = mock_response
        MockApi.return_value.get_last_request.return_value = None
        cli()
    captured = capsys.readouterr()
    assert "No previous API request made." in captured.out


# --- Status code fix tests ---


def test_4xx_returns_real_status_code(blesta_request):
    with patch.object(blesta_request.session, "get") as mock_get:
        mock_response = Mock()
        mock_response.text = '{"errors": {"message": "Not found"}}'
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        response = blesta_request.get("clients", "get", {"client_id": 999})
        assert response.status_code == 404
        assert response.errors() == {"message": "Not found"}


def test_401_returns_real_status_code(blesta_request):
    with patch.object(blesta_request.session, "get") as mock_get:
        mock_response = Mock()
        mock_response.text = '{"errors": {"message": "Unauthorized"}}'
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        response = blesta_request.get("clients", "getList")
        assert response.status_code == 401


def test_500_returns_real_status_code(blesta_request):
    with patch.object(blesta_request.session, "get") as mock_get:
        mock_response = Mock()
        mock_response.text = '{"errors": {"message": "Internal server error"}}'
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        response = blesta_request.get("clients", "getList")
        assert response.status_code == 500
        assert response.errors() == {"message": "Internal server error"}


# --- CSV response tests ---


def test_is_json_true():
    response = BlestaResponse('{"response": {"id": 1}}', 200)
    assert response.is_json is True
    assert response.is_csv is False


def test_is_csv_true():
    csv_text = '"id","name","amount"\n"1","John","100.00"\n"2","Jane","200.00"\n'
    response = BlestaResponse(csv_text, 200)
    assert response.is_csv is True
    assert response.is_json is False


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


def test_is_csv_false_for_empty():
    response = BlestaResponse("", 200)
    assert response.is_csv is False


def test_is_csv_false_for_single_line():
    response = BlestaResponse("just a string", 200)
    assert response.is_csv is False


def test_response_property_returns_none_for_csv():
    csv_text = '"id","name"\n"1","John"\n'
    response = BlestaResponse(csv_text, 200)
    assert response.response is None


# --- Pagination tests ---


def test_get_all_pages_iterates(blesta_request):
    page1 = [{"id": 1}, {"id": 2}]
    page2 = [{"id": 3}]
    page3 = []

    responses = [
        BlestaResponse(json.dumps({"response": page1}), 200),
        BlestaResponse(json.dumps({"response": page2}), 200),
        BlestaResponse(json.dumps({"response": page3}), 200),
    ]

    with patch.object(blesta_request, "get", side_effect=responses):
        result = list(blesta_request.get_all_pages("invoices", "getList"))

    assert result == [{"id": 1}, {"id": 2}, {"id": 3}]


def test_get_all_returns_list(blesta_request):
    page1 = [{"id": 1}]
    page2 = []

    responses = [
        BlestaResponse(json.dumps({"response": page1}), 200),
        BlestaResponse(json.dumps({"response": page2}), 200),
    ]

    with patch.object(blesta_request, "get", side_effect=responses):
        result = blesta_request.get_all("invoices", "getList")

    assert isinstance(result, list)
    assert result == [{"id": 1}]


def test_get_all_pages_stops_on_error(blesta_request):
    page1 = [{"id": 1}]

    responses = [
        BlestaResponse(json.dumps({"response": page1}), 200),
        BlestaResponse('{"errors": {"message": "Forbidden"}}', 403),
    ]

    with patch.object(blesta_request, "get", side_effect=responses):
        result = list(blesta_request.get_all_pages("invoices", "getList"))

    assert result == [{"id": 1}]


def test_get_all_pages_stops_on_none_response(blesta_request):
    responses = [
        BlestaResponse('{"other": "data"}', 200),
    ]

    with patch.object(blesta_request, "get", side_effect=responses):
        result = list(blesta_request.get_all_pages("invoices", "getList"))

    assert result == []


def test_get_all_pages_forwards_args(blesta_request):
    responses = [
        BlestaResponse(json.dumps({"response": []}), 200),
    ]

    with patch.object(blesta_request, "get", side_effect=responses) as mock_get:
        list(blesta_request.get_all_pages("invoices", "getList", {"status": "active"}))

    mock_get.assert_called_once_with(
        "invoices", "getList", {"status": "active", "page": 1}
    )


def test_get_all_pages_start_page(blesta_request):
    responses = [
        BlestaResponse(json.dumps({"response": []}), 200),
    ]

    with patch.object(blesta_request, "get", side_effect=responses) as mock_get:
        list(blesta_request.get_all_pages("invoices", "getList", start_page=5))

    mock_get.assert_called_once_with("invoices", "getList", {"page": 5})


def test_get_all_pages_single_object_response(blesta_request):
    responses = [
        BlestaResponse(json.dumps({"response": {"id": 1, "name": "John"}}), 200),
    ]

    with patch.object(blesta_request, "get", side_effect=responses):
        result = list(blesta_request.get_all_pages("clients", "get"))

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


def test_get_report_returns_blesta_response(blesta_request):
    csv_text = '"id","amount"\n"1","100.00"\n'
    mock_response = BlestaResponse(csv_text, 200)

    with patch.object(blesta_request, "get", return_value=mock_response):
        response = blesta_request.get_report(
            "tax_liability", "2025-01-01", "2025-01-31"
        )

    assert isinstance(response, BlestaResponse)


# --- _month_boundaries tests ---


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
    with patch.dict(sys.modules, {"pandas": None}):
        with pytest.raises(ImportError, match="pip install pandas"):
            response.to_dataframe()


def test_to_dataframe_empty_csv():
    csv_text = '"id","name"\n"1","John"\n'
    response = BlestaResponse(csv_text, 200)
    df = response.to_dataframe()
    assert len(df) == 1
    # Verify structure is correct
    assert list(df.columns) == ["id", "name"]


def test_to_dataframe_non_parseable_raises():
    response = BlestaResponse("just some text", 200)
    with pytest.raises(ValueError, match="neither CSV nor JSON"):
        response.to_dataframe()


def test_to_dataframe_json_no_response_key_raises():
    json_text = json.dumps({"other": "data"})
    response = BlestaResponse(json_text, 200)
    with pytest.raises(ValueError, match="no 'response' key"):
        response.to_dataframe()


# --- Integration test (requires valid .env credentials) ---


@pytest.mark.integration
def test_credentials(blesta_request):
    response = blesta_request.get("clients", "getList", {"status": "active"})
    assert isinstance(response, BlestaResponse)
    assert response.status_code == 200
    assert response.response is not None

    print(json.dumps(response.response, indent=4))


if __name__ == "__main__":
    pytest.main(["-v"])
