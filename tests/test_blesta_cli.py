import subprocess
import unittest
import json

class TestBlestaCLI(unittest.TestCase):

    def run_cli_command(self, model, method, params=None, last_request=False):
        command = ["python", "blesta_cli.py", "--model", model, "--method", method]
        if params:
            command.extend(["--params"] + params)
        if last_request:
            command.append("--last-request")
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return result

    def test_get_specific_client(self):
        result = self.run_cli_command("clients", "get", ["client_id=1"], last_request=True)
        self.assertEqual(result.returncode, 0)

        # Print the JSON output for debugging
        try:
            response_json = json.loads(result.stdout)
            print("\nResponse JSON:")
            print(json.dumps(response_json, indent=4))
        except json.JSONDecodeError:
            print("\nFailed to decode JSON response. Raw output:")
            print(result.stdout)

        self.assertIn("id", result.stdout.lower(), msg=f"Unexpected error: {result.stdout}")

if __name__ == "__main__":
    unittest.main(verbosity=2)