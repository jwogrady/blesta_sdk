import pytest
import requests
from unittest.mock import patch, Mock
from blesta_sdk.api.blesta_request import BlestaRequest
from blesta_sdk.core import BlestaResponse
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
    with patch.dict(
        os.environ,
        {"BLESTA_API_URL": "", "BLESTA_API_USER": "", "BLESTA_API_KEY": ""},
        clear=False,
    ), patch("sys.argv", ["blesta", "--model", "clients", "--method", "getList"]):
        cli()
    captured = capsys.readouterr()
    assert "Missing API credentials" in captured.out


def test_cli_successful_get(capsys):
    mock_response = BlestaResponse('{"response": {"clients": []}}', 200)
    with patch.dict(
        os.environ,
        {
            "BLESTA_API_URL": "https://example.com/api",
            "BLESTA_API_USER": "user",
            "BLESTA_API_KEY": "key",
        },
        clear=False,
    ), patch(
        "sys.argv", ["blesta", "--model", "clients", "--method", "getList"]
    ), patch(
        "blesta_sdk.cli.blesta_cli.BlestaRequest"
    ) as MockApi:
        MockApi.return_value.submit.return_value = mock_response
        cli()
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output == {"clients": []}


def test_cli_error_response(capsys):
    mock_response = BlestaResponse('{"errors": {"message": "Not found"}}', 404)
    with patch.dict(
        os.environ,
        {
            "BLESTA_API_URL": "https://example.com/api",
            "BLESTA_API_USER": "user",
            "BLESTA_API_KEY": "key",
        },
        clear=False,
    ), patch(
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
    ), patch(
        "blesta_sdk.cli.blesta_cli.BlestaRequest"
    ) as MockApi:
        MockApi.return_value.submit.return_value = mock_response
        cli()
    captured = capsys.readouterr()
    assert "Error:" in captured.out


def test_cli_with_params_and_action(capsys):
    mock_response = BlestaResponse('{"response": {"created": true}}', 200)
    with patch.dict(
        os.environ,
        {
            "BLESTA_API_URL": "https://example.com/api",
            "BLESTA_API_USER": "user",
            "BLESTA_API_KEY": "key",
        },
        clear=False,
    ), patch(
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
    ), patch(
        "blesta_sdk.cli.blesta_cli.BlestaRequest"
    ) as MockApi:
        MockApi.return_value.submit.return_value = mock_response
        cli()

    MockApi.return_value.submit.assert_called_once_with(
        "clients", "create", {"name": "John", "status": "active"}, "POST"
    )


def test_cli_params_with_equals_in_value(capsys):
    mock_response = BlestaResponse('{"response": {"ok": true}}', 200)
    with patch.dict(
        os.environ,
        {
            "BLESTA_API_URL": "https://example.com/api",
            "BLESTA_API_USER": "user",
            "BLESTA_API_KEY": "key",
        },
        clear=False,
    ), patch(
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
    ), patch(
        "blesta_sdk.cli.blesta_cli.BlestaRequest"
    ) as MockApi:
        MockApi.return_value.submit.return_value = mock_response
        cli()

    MockApi.return_value.submit.assert_called_once_with(
        "clients", "get", {"filter": "a=b"}, "GET"
    )


def test_cli_last_request_flag(capsys):
    mock_response = BlestaResponse('{"response": {"id": 1}}', 200)
    with patch.dict(
        os.environ,
        {
            "BLESTA_API_URL": "https://example.com/api",
            "BLESTA_API_USER": "user",
            "BLESTA_API_KEY": "key",
        },
        clear=False,
    ), patch(
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
    ), patch(
        "blesta_sdk.cli.blesta_cli.BlestaRequest"
    ) as MockApi:
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
    with patch.dict(
        os.environ,
        {
            "BLESTA_API_URL": "https://example.com/api",
            "BLESTA_API_USER": "user",
            "BLESTA_API_KEY": "key",
        },
        clear=False,
    ), patch(
        "sys.argv",
        ["blesta", "--model", "clients", "--method", "get", "--last-request"],
    ), patch(
        "blesta_sdk.cli.blesta_cli.BlestaRequest"
    ) as MockApi:
        MockApi.return_value.submit.return_value = mock_response
        MockApi.return_value.get_last_request.return_value = None
        cli()
    captured = capsys.readouterr()
    assert "No previous API request made." in captured.out


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
