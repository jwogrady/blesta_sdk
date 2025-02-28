import pytest
import requests
from unittest.mock import patch, Mock
from blesta_sdk.api.blesta_request import BlestaRequest
from blesta_sdk.core import BlestaResponse
from dotenv import load_dotenv
import os
import json

# Load environment variables from .env file
load_dotenv()

@pytest.fixture
def blesta_request():
    url = os.getenv("BLESTA_API_URL", "https://aware.status26.com/api")
    user = os.getenv("BLESTA_API_USER", "user")
    key = os.getenv("BLESTA_API_KEY", "key")
    return BlestaRequest(url, user, key)

def test_get_request(blesta_request):
    with patch.object(blesta_request.session, 'get') as mock_get:
        mock_response = Mock()
        mock_response.text = '{"success": true}'
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        response = blesta_request.get("clients", "getList", {"status": "active"})
        assert isinstance(response, BlestaResponse)
        assert response.status_code == 200
        assert response.raw == '{"success": true}'

def test_post_request(blesta_request):
    with patch.object(blesta_request.session, 'post') as mock_post:
        mock_response = Mock()
        mock_response.text = '{"success": true}'
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        response = blesta_request.post("clients", "create", {"name": "John Doe"})
        assert isinstance(response, BlestaResponse)
        assert response.status_code == 200
        assert response.raw == '{"success": true}'

def test_put_request(blesta_request):
    with patch.object(blesta_request.session, 'put') as mock_put:
        mock_response = Mock()
        mock_response.text = '{"success": true}'
        mock_response.status_code = 200
        mock_put.return_value = mock_response

        response = blesta_request.put("clients", "update", {"client_id": 1, "name": "John Doe"})
        assert isinstance(response, BlestaResponse)
        assert response.status_code == 200
        assert response.raw == '{"success": true}'

def test_delete_request(blesta_request):
    with patch.object(blesta_request.session, 'delete') as mock_delete:
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
    with patch.object(blesta_request.session, 'get', side_effect=requests.RequestException("Error")):
        response = blesta_request.get("clients", "getList")
        assert isinstance(response, BlestaResponse)
        assert response.status_code == 500
        assert "Error" in response.raw

def test_get_last_request(blesta_request):
    with patch.object(blesta_request.session, 'get') as mock_get:
        mock_response = Mock()
        mock_response.text = '{"success": true}'
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        blesta_request.get("clients", "getList", {"status": "active"})
        last_request = blesta_request.get_last_request()
        assert last_request["url"] == f"{os.getenv('BLESTA_API_URL', 'https://aware.status26.com/api')}/clients/getList.json"
        assert last_request["args"] == {"status": "active"}

def test_format_response_valid_json():
    response = BlestaResponse('{"response": {"success": true}}', 200)
    assert response.response == {"success": True}

def test_format_response_invalid_json():
    response = BlestaResponse('Invalid JSON', 200)
    assert response.errors() == {"error": "Invalid JSON response"}

def test_blesta_response_errors():
    response = BlestaResponse('{"errors": {"message": "Error occurred"}}', 400)
    assert response.errors() == {"message": "Error occurred"}

def test_credentials(blesta_request):
    # This test will make an actual API request to verify the credentials
    response = blesta_request.get("clients", "getList", {"status": "active"})
    assert isinstance(response, BlestaResponse)
    assert response.status_code == 200
    assert response.response is not None

    # Print the response in pretty JSON format
    print(json.dumps(response.response, indent=4))

if __name__ == "__main__":
    pytest.main(["-v"])
