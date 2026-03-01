import os
from unittest.mock import patch

import pytest

from blesta_sdk import BlestaRequest

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


@pytest.fixture
def blesta_request():
    url = os.getenv("BLESTA_API_URL", "https://test.example.com/api")
    user = os.getenv("BLESTA_API_USER", "user")
    key = os.getenv("BLESTA_API_KEY", "key")
    return BlestaRequest(url, user, key)


@pytest.fixture
def cli_env():
    """Set CLI environment variables for non-integration CLI tests."""
    with patch.dict(
        os.environ,
        {
            "BLESTA_API_URL": "https://example.com/api",
            "BLESTA_API_USER": "user",
            "BLESTA_API_KEY": "key",
        },
        clear=False,
    ):
        yield
