import subprocess
import pytest
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Ensure environment variables are loaded
def test_env_variables():
    assert os.getenv("BLESTA_API_URL") is not None, "BLESTA_API_URL is not set"
    assert os.getenv("BLESTA_API_USER") is not None, "BLESTA_API_USER is not set"
    assert os.getenv("BLESTA_API_KEY") is not None, "BLESTA_API_KEY is not set"

# Test cases matching README examples
@pytest.mark.parametrize("command", [
    # Clients Model
    "blesta-cli --model clients --method getList --params status=active --last-request",
    "blesta-cli --model clients --method get --params client_id=1 --last-request",
    # Services Model
    "blesta-cli --model services --method getList --params status=active --last-request",
    "blesta-cli --model services --method getAll --params client_id=1 --last-request"
])
def test_blesta_cli(command):
    """Runs a CLI command and checks if it executes successfully."""
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    print("--- Command Output ---")
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)

    assert result.returncode == 0, f"Command failed with exit code {result.returncode}"

    print(f"[SUCCESS] Command '{command}' executed successfully.")

if __name__ == "__main__":
    pytest.main(["-v"])
