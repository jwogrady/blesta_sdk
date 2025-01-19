import unittest
from unittest.mock import patch, MagicMock
import argparse
import io
from blesta_sdk.cli.blesta_cli import cli
from dotenv import load_dotenv
import os

if os.path.exists('.env'):
    load_dotenv()

# Import the cli function from blesta_cli

class TestBlestaCli(unittest.TestCase):

    @patch('blesta_sdk.cli.blesta_cli.BlestaApi')
    @patch('blesta_sdk.cli.blesta_cli.os.getenv')
    @patch('blesta_sdk.cli.blesta_cli.argparse.ArgumentParser.parse_args')
    def test_cli_successful_response(self, mock_parse_args, mock_getenv, MockBlestaApi):
        # Mock command-line arguments
        mock_parse_args.return_value = argparse.Namespace(
            model='clients', method='getList', action='GET', params=['id=1'], last_request=False
        )

        # Mock environment variables
        mock_getenv.side_effect = lambda key: {
            'BLESTA_API_URL': 'http://example.com/api',
            'BLESTA_API_USER': 'user',
            'BLESTA_API_KEY': 'key'
        }.get(key)

        # Mock BlestaApi response
        mock_api_instance = MockBlestaApi.return_value
        mock_api_instance.submit.return_value = MagicMock(response_code=200, response={'data': 'test'})
        mock_api_instance.get_last_request.return_value = {'url': 'http://example.com/api', 'args': {'id': 1}}

        # Capture stdout
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            cli()
            output = mock_stdout.getvalue()

        # Assertions
        self.assertIn('"data": "test"', output)

    @patch('blesta_sdk.cli.blesta_cli.BlestaApi')
    @patch('blesta_sdk.cli.blesta_cli.os.getenv')
    @patch('blesta_sdk.cli.blesta_cli.argparse.ArgumentParser.parse_args')
    def test_cli_missing_credentials(self, mock_parse_args, mock_getenv, _):
        # Mock command-line arguments
        mock_parse_args.return_value = argparse.Namespace(
            model='clients', method='getList', action='GET', params=['id=1'], last_request=False
        )

        # Mock environment variables to return None
        mock_getenv.side_effect = lambda _: None

        # Capture stdout
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            cli()
            output = mock_stdout.getvalue()

        # Assertions
        self.assertIn("Error: Missing API credentials in .env file.", output)

    @patch('blesta_sdk.cli.blesta_cli.BlestaApi')
    @patch('blesta_sdk.cli.blesta_cli.os.getenv')
    @patch('blesta_sdk.cli.blesta_cli.argparse.ArgumentParser.parse_args')
    def test_cli_error_response(self, mock_parse_args, mock_getenv, MockBlestaApi):
        # Mock command-line arguments
        mock_parse_args.return_value = argparse.Namespace(
            model='clients', method='getList', action='GET', params=['id=1'], last_request=False
        )

        # Mock environment variables
        mock_getenv.side_effect = lambda key: {
            'BLESTA_API_URL': 'http://example.com/api',
            'BLESTA_API_USER': 'user',
            'BLESTA_API_KEY': 'key'
        }.get(key)

        # Mock BlestaApi response
        mock_api_instance = MockBlestaApi.return_value
        mock_api_instance.submit.return_value = MagicMock(response_code=400, errors=lambda: 'Bad Request')

        # Capture stdout
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            cli()
            output = mock_stdout.getvalue()

        # Assertions
        self.assertIn("Error: Bad Request", output)

    @patch('blesta_sdk.cli.blesta_cli.BlestaApi')
    @patch('blesta_sdk.cli.blesta_cli.os.getenv')
    @patch('blesta_sdk.cli.blesta_cli.argparse.ArgumentParser.parse_args')
    def test_cli_last_request(self, mock_parse_args, mock_getenv, MockBlestaApi):
        # Mock command-line arguments
        mock_parse_args.return_value = argparse.Namespace(
            model='clients', method='getList', action='GET', params=['id=1'], last_request=True
        )

        # Mock environment variables
        mock_getenv.side_effect = lambda key: {
            'BLESTA_API_URL': 'http://example.com/api',
            'BLESTA_API_USER': 'user',
            'BLESTA_API_KEY': 'key'
        }.get(key)

        # Mock BlestaApi response
        mock_api_instance = MockBlestaApi.return_value
        mock_api_instance.submit.return_value = MagicMock(response_code=200, response={'data': 'test'})
        mock_api_instance.get_last_request.return_value = {'url': 'http://example.com/api', 'args': {'id': 1}}

        # Capture stdout
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            cli()
            output = mock_stdout.getvalue()

        # Assertions
        self.assertIn("Last Request URL: http://example.com/api", output)
        self.assertIn("Last Request Parameters: {'id': 1}", output)

if __name__ == '__main__':
    unittest.main()